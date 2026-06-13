"""Local translation service backed by Argos Translate."""
import asyncio
from pathlib import Path
from functools import lru_cache

from bs4 import BeautifulSoup, NavigableString


class ArgosTranslateError(Exception):
    """Raised when local Argos translation cannot be completed."""


LANGUAGE_MAP = {
    "zh-CN": "zh",
    "zh-TW": "zh",
    "zh": "zh",
    "en-US": "en",
    "en-GB": "en",
    "en": "en",
    "ja": "ja",
    "jp": "ja",
    "ko": "ko",
    "kr": "ko",
}


def normalize_argos_language(language: str | None, default: str = "en") -> str:
    """Normalize app language codes into Argos language codes."""
    normalized = (language or default).strip()
    if not normalized:
        normalized = default
    return LANGUAGE_MAP.get(normalized, LANGUAGE_MAP.get(normalized.lower(), normalized.lower()))


@lru_cache(maxsize=1)
def _get_translate_module():
    try:
        import argostranslate.translate as argos_translate
    except ImportError as exc:
        raise ArgosTranslateError(
            "Argos Translate 未安装，请在后端环境安装 argostranslate"
        ) from exc
    return argos_translate


@lru_cache(maxsize=1)
def _get_package_module():
    try:
        import argostranslate.package as argos_package
    except ImportError as exc:
        raise ArgosTranslateError(
            "Argos Translate 未安装，请在后端环境安装 argostranslate"
        ) from exc
    return argos_package


def _clear_argos_runtime_cache() -> None:
    try:
        argos_translate = _get_translate_module()
        cache_clear = getattr(argos_translate.get_installed_languages, "cache_clear", None)
        if callable(cache_clear):
            cache_clear()
    except ArgosTranslateError:
        pass
    _get_translate_module.cache_clear()
    _get_package_module.cache_clear()


def _is_translation_package(package) -> bool:
    return (
        getattr(package, "type", "translate") == "translate"
        and bool(getattr(package, "from_code", None))
        and bool(getattr(package, "to_code", None))
    )


def _package_to_dict(package, installed: bool) -> dict:
    source_language = getattr(package, "from_code", "") or ""
    target_language = getattr(package, "to_code", "") or ""
    return {
        "source_language": source_language,
        "source_name": getattr(package, "from_name", None) or source_language,
        "target_language": target_language,
        "target_name": getattr(package, "to_name", None) or target_language,
        "package_version": getattr(package, "package_version", None),
        "argos_version": getattr(package, "argos_version", None),
        "package_type": getattr(package, "type", None) or "translate",
        "installed": installed,
    }


def _sort_packages(packages: list[dict]) -> list[dict]:
    return sorted(
        packages,
        key=lambda package: (
            package["source_language"],
            package["target_language"],
            package.get("package_version") or "",
        ),
    )


def _package_index_exists(argos_package) -> bool:
    settings = getattr(argos_package, "settings", None)
    index_path = getattr(settings, "local_package_index", None)
    return bool(index_path and Path(index_path).exists())


def _load_available_packages(refresh: bool = False):
    argos_package = _get_package_module()
    if refresh or not _package_index_exists(argos_package):
        argos_package.update_package_index()

    if not _package_index_exists(argos_package):
        raise ArgosTranslateError(
            "Argos 语言包索引不可用，请检查服务器网络后刷新语言包列表"
        )

    try:
        return [
            package
            for package in argos_package.get_available_packages()
            if _is_translation_package(package)
        ]
    except Exception as exc:
        raise ArgosTranslateError(f"读取 Argos 语言包索引失败: {exc}") from exc


def _get_installed_packages():
    argos_package = _get_package_module()
    try:
        return [
            package
            for package in argos_package.get_installed_packages()
            if _is_translation_package(package)
        ]
    except Exception as exc:
        raise ArgosTranslateError(f"读取已安装 Argos 语言包失败: {exc}") from exc


def _find_package(packages, source_language: str, target_language: str):
    return next(
        (
            package
            for package in packages
            if getattr(package, "from_code", None) == source_language
            and getattr(package, "to_code", None) == target_language
        ),
        None,
    )


def _get_translation(source_language: str, target_language: str):
    argos_translate = _get_translate_module()
    installed_languages = argos_translate.get_installed_languages()

    def find_translation():
        from_language = next(
            (language for language in installed_languages if language.code == source_language),
            None,
        )
        to_language = next(
            (language for language in installed_languages if language.code == target_language),
            None,
        )
        if not from_language or not to_language:
            return None, from_language, to_language
        return from_language.get_translation(to_language), from_language, to_language

    translation, from_language, to_language = find_translation()
    if translation:
        return translation

    cache_clear = getattr(argos_translate.get_installed_languages, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()
        installed_languages = argos_translate.get_installed_languages()
        translation, from_language, to_language = find_translation()
        if translation:
            return translation

    if not from_language or not to_language:
        available = ", ".join(sorted(language.code for language in installed_languages)) or "无"
        raise ArgosTranslateError(
            f"Argos 语言包未安装: {source_language} -> {target_language} "
            f"(已安装语言: {available})"
        )

    raise ArgosTranslateError(f"Argos 语言包未安装: {source_language} -> {target_language}")


def list_argos_packages_sync(refresh: bool = False) -> dict:
    """List installed and available Argos translation packages."""
    installed_packages = _get_installed_packages()
    installed_pairs = {
        (package.from_code, package.to_code)
        for package in installed_packages
        if getattr(package, "from_code", None) and getattr(package, "to_code", None)
    }

    available_error = None
    try:
        available_packages = _load_available_packages(refresh=refresh)
    except ArgosTranslateError as exc:
        available_packages = []
        available_error = str(exc)

    return {
        "installed": _sort_packages(
            [_package_to_dict(package, installed=True) for package in installed_packages]
        ),
        "available": _sort_packages(
            [
                {
                    **_package_to_dict(package, installed=(package.from_code, package.to_code) in installed_pairs),
                }
                for package in available_packages
            ]
        ),
        "available_error": available_error,
    }


async def list_argos_packages(refresh: bool = False) -> dict:
    return await asyncio.to_thread(list_argos_packages_sync, refresh)


def install_argos_package_sync(source_language: str, target_language: str) -> dict:
    source = normalize_argos_language(source_language, default="en")
    target = normalize_argos_language(target_language, default="zh")
    if source == target:
        raise ArgosTranslateError("源语言和目标语言不能相同")

    installed_package = _find_package(_get_installed_packages(), source, target)
    if installed_package:
        return _package_to_dict(installed_package, installed=True)

    available_packages = _load_available_packages(refresh=False)
    package_to_install = _find_package(available_packages, source, target)
    if not package_to_install:
        available_packages = _load_available_packages(refresh=True)
        package_to_install = _find_package(available_packages, source, target)

    if not package_to_install:
        raise ArgosTranslateError(f"未找到 Argos 语言包: {source} -> {target}")

    download_path = None
    try:
        argos_package = _get_package_module()
        download_path = package_to_install.download()
        argos_package.install_from_path(download_path)
    except Exception as exc:
        raise ArgosTranslateError(f"安装 Argos 语言包失败: {exc}") from exc
    finally:
        if download_path and hasattr(download_path, "exists") and download_path.exists():
            try:
                download_path.unlink()
            except OSError:
                pass

    _clear_argos_runtime_cache()
    installed_package = _find_package(_get_installed_packages(), source, target)
    return _package_to_dict(installed_package or package_to_install, installed=True)


async def install_argos_package(source_language: str, target_language: str) -> dict:
    return await asyncio.to_thread(
        install_argos_package_sync,
        source_language,
        target_language,
    )


def uninstall_argos_package_sync(source_language: str, target_language: str) -> dict:
    source = normalize_argos_language(source_language, default="en")
    target = normalize_argos_language(target_language, default="zh")
    package_to_remove = _find_package(_get_installed_packages(), source, target)
    if not package_to_remove:
        return {
            "success": True,
            "message": f"Argos 语言包未安装: {source} -> {target}",
        }

    try:
        _get_package_module().uninstall(package_to_remove)
    except Exception as exc:
        raise ArgosTranslateError(f"卸载 Argos 语言包失败: {exc}") from exc

    _clear_argos_runtime_cache()
    return {
        "success": True,
        "message": f"Argos 语言包已卸载: {source} -> {target}",
    }


async def uninstall_argos_package(source_language: str, target_language: str) -> dict:
    return await asyncio.to_thread(
        uninstall_argos_package_sync,
        source_language,
        target_language,
    )


def test_argos_package_sync(
    source_language: str,
    target_language: str,
    text: str | None = None,
) -> dict:
    source = normalize_argos_language(source_language, default="en")
    target = normalize_argos_language(target_language, default="zh")
    sample_text = (text or "Hello").strip() or "Hello"
    try:
        translation = ArgosTranslateService(source).translate_sync(sample_text, target)
    except ArgosTranslateError as exc:
        return {
            "success": False,
            "message": str(exc),
            "translation": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "message": f"Argos 翻译测试失败: {exc}",
            "translation": None,
        }

    return {
        "success": True,
        "message": f"Argos 翻译可用: {source} -> {target}",
        "translation": translation,
    }


async def test_argos_package(
    source_language: str,
    target_language: str,
    text: str | None = None,
) -> dict:
    return await asyncio.to_thread(
        test_argos_package_sync,
        source_language,
        target_language,
        text,
    )


class ArgosTranslateService:
    """Translate text locally with installed Argos language packages."""

    def __init__(self, source_language: str | None = None):
        self.source_language = normalize_argos_language(source_language, default="en")

    def translate_sync(self, text: str, target_language: str) -> str:
        """Translate text synchronously, preserving simple HTML structure when present."""
        if not text:
            return ""

        target = normalize_argos_language(target_language, default="zh")
        if self.source_language == target:
            return text

        translation = _get_translation(self.source_language, target)
        if "<" in text and ">" in text:
            return self._translate_html(text, translation)
        return translation.translate(text)

    async def translate(self, text: str, target_language: str) -> str:
        """Translate text without blocking the async event loop."""
        return await asyncio.to_thread(self.translate_sync, text, target_language)

    def translate_article_sync(
        self,
        title: str,
        content: str,
        target_language: str,
    ) -> tuple[str, str]:
        return (
            self.translate_sync(title, target_language) if title else "",
            self.translate_sync(content, target_language) if content else "",
        )

    async def translate_article(
        self,
        title: str,
        content: str,
        target_language: str,
    ) -> tuple[str, str]:
        return await asyncio.to_thread(
            self.translate_article_sync,
            title,
            content,
            target_language,
        )

    def _translate_html(self, html: str, translation) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for node in soup.find_all(string=True):
            if not isinstance(node, NavigableString):
                continue
            if node.parent and node.parent.name in {"script", "style", "code", "pre"}:
                continue
            original = str(node)
            if not original.strip():
                continue
            leading = original[: len(original) - len(original.lstrip())]
            trailing = original[len(original.rstrip()) :]
            translated = translation.translate(original.strip())
            node.replace_with(f"{leading}{translated}{trailing}")
        return str(soup)

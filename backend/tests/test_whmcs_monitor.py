from app.utils.whmcs_monitor import (
    extract_whmcs_status_from_content,
    build_whmcs_status_content,
    parse_whmcs_product_state,
)


def test_parse_whmcs_out_of_stock_page():
    html = """
    <html>
      <script>var csrfToken = 'token', whmcsBaseUrl = '';</script>
      <body class="page-order page-error">
        <h1>Oops, there's a problem...</h1>
        <div class="message message-danger">
          <h2>Out of Stock</h2>
          <p>We are currently out of stock on this item so orders for it have been suspended.</p>
        </div>
      </body>
    </html>
    """

    state = parse_whmcs_product_state(
        html,
        "https://example.com/index.php?rp=/store/vps/chef-special",
    )

    assert state.title == "Chef Special"
    assert state.status == "out_of_stock"
    assert state.status_label == "下架/缺货"


def test_parse_whmcs_in_stock_order_form():
    html = """
    <html>
      <script>var csrfToken = 'token', whmcsBaseUrl = '';</script>
      <body class="page-order">
        <h1>NVMe VPS 1G</h1>
        <form method="post" action="/cart.php?a=add&pid=42">
          <input type="hidden" name="pid" value="42" />
          <button type="submit">Order Now</button>
        </form>
      </body>
    </html>
    """

    state = parse_whmcs_product_state(html, "https://example.com/store/vps/nvme-vps-1g")
    content = build_whmcs_status_content(state, "https://example.com/store/vps/nvme-vps-1g")

    assert state.title == "NVMe VPS 1G"
    assert state.status == "in_stock"
    assert extract_whmcs_status_from_content(content) == "in_stock"

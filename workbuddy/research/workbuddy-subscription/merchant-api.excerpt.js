// Source: https://static.workbuddy.cn/web/open/497edfa5e57a20027b77597f84a4b1d49795f325/_next/static/chunks/4253-ad2ae83e05f40ebb.js
async function eJ(e,t){let n=await e.request("".concat("/api/v1/open-platform/charge-developer/merchant/withdraw","?partyId=").concat(encodeURIComponent(t)),{method:"POST"});return{initiated:(null==n?void 0:n.result)===1}}
class eG{registerSubMerchant(e){return this.httpClient.request("/api/v1/open-platform/charge-developer/merchant/register-sub-merchant",{method:"POST",body:JSON.stringify(e)})}
getCertStatus(e,t){let n="/api/v1/open-platform/charge-developer/merchant/cert-status?partyId=".concat(encodeURIComponent(e));return t&&(n+="&resourceId=".concat(encodeURIComponent(t))),this.httpClient.request(n,{method:"GET"}).then(eO)}
getSubMerchantStatus(e){return eN(this.httpClient,e)}
resolveBankCard(e){return this.httpClient.request("/api/v1/open-platform/charge-developer/merchant/bank-name?cardNo=".concat(encodeURIComponent(e)),{method:"GET"})}
getBills(e){return ez(this.httpClient,e)}
getOrderSources(e){var t;return t=this.httpClient,t.request("".concat("/api/v1/open-platform/charge-developer/merchant/order-sources","?partyId=").concat(encodeURIComponent(e)),{method:"GET"}).then(e=>{var t;return(null!=(t=null==e?void 0:e.sources)?t:[]).map(e=>{var t,n,i;return{resourceId:null!=(t=e.resourceId)?t:"",goodsType:null!=(n=e.goodsType)?n:0,goodsName:null!=(i=e.goodsName)?i:""}})})}
getOverviewData(e){return ej(this.httpClient,e)}
getAccountInfo(e){var t;return t=this.httpClient,t.request("".concat("/api/v1/open-platform/charge-developer/merchant/account","?partyId=").concat(encodeURIComponent(e)),{method:"GET"})}
getGoodsPriceChangeQuota(e,t,n){var i=this.httpClient;let r=new URLSearchParams({partyId:e,resourceId:t,payMode:String(n)});return i.request("".concat("/api/v1/open-platform/charge-developer/merchant/goods-price-change-quota","?").concat(r.toString()),{method:"GET"})}
updateGoods(e){var t=this.httpClient;let{assetId:n,...i}=e;return t.request("".concat("/api/v2/open-platform/capabilities","/").concat(encodeURIComponent(n),"/pay"),{method:"POST",body:JSON.stringify(i)}).then(e=>{var t;return{msg:null!=(t=null==e?void 0:e.msg)?t:""}})}
requestWithdraw(e){return eJ(this.httpClient,e)}
constructor(e){this.httpClient=e}}
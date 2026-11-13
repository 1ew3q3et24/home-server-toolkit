(function(){
var lines=[], done=false;
function L(s){lines.push(s);}
function finish(good,msg){
  if(done)return; done=true;
  var r=document.getElementById("res");
  r.className=good?"ok":"bad"; r.textContent=msg;
  lines.push("RESULT: "+(good?"SUPPORTED":"NOT_SUPPORTED"));
  document.getElementById("log").textContent=lines.join("\n");
  try{ if(window.parent&&window.parent!==window) window.parent.postMessage({type:"enc-check",ok:!!good,ua:navigator.userAgent},"*"); }catch(e){}
}
L("UA: "+navigator.userAgent);
L("crypto: "+(!!window.crypto));
L("crypto.subtle: "+!!(window.crypto&&window.crypto.subtle));
L("TextEncoder: "+(typeof TextEncoder!=="undefined"));
if(!(window.crypto&&window.crypto.subtle&&typeof crypto.subtle.generateKey==="function")){ finish(false,"本设备不支持端到端加密 (无 WebCrypto)"); return; }
(async function(){
  try{
    var a=await crypto.subtle.generateKey({name:"ECDH",namedCurve:"P-256"},true,["deriveBits"]);
    var b=await crypto.subtle.generateKey({name:"ECDH",namedCurve:"P-256"},true,["deriveBits"]);
    var bits=await crypto.subtle.deriveBits({name:"ECDH",public:b.publicKey},a.privateKey,256);
    var key=await crypto.subtle.importKey("raw",bits,{name:"AES-GCM"},false,["encrypt","decrypt"]);
    var iv=crypto.getRandomValues(new Uint8Array(12));
    var ct=await crypto.subtle.encrypt({name:"AES-GCM",iv:iv},key,new TextEncoder().encode("ping"));
    var pt=await crypto.subtle.decrypt({name:"AES-GCM",iv:iv},key,ct);
    var txt=new TextDecoder().decode(pt);
    L("ECDH(P-256)+AES-GCM roundtrip: "+txt);
    finish(txt==="ping", txt==="ping"?"本设备支持端到端加密 OK":"加密往返结果异常");
  }catch(e){ L("err: "+e); finish(false,"自检出错: "+e); }
})();
})();

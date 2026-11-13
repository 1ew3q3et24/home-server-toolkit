# WEB-08 改进建议 — 用 DOM API / textContent 渲染，禁止把 MC 名拼进 innerHTML

## 位置
- `cloud/var/www/mcverify/index.php:465-469`（`loadMine()`）
- 对照正确写法：同文件 `:381`（服务端 `htmlspecialchars`）、`lib.php` 无客户端转义工具

## 推荐改法（A：DOM 构建，推荐——不依赖手写转义）

```diff
 q('c').addEventListener('input',function(){q('c').value=q('c').value.replace(/[^0-9-]/g,'')});
 function loadMine(){fetch('/?action=mine',{credentials:'same-origin'}).then(function(r){return r.json()}).then(function(j){
   if(!j.ok)return;var box=q('mylog');if(!j.items.length){box.textContent='（暂无）';return}
-  box.innerHTML=j.items.map(function(it){
-    var s=it.submitted_at?'<span class="pill p-ok">已通过</span>':(it.expired?'<span class="pill p-bad">已过期</span>':'<span class="pill p-wait">待验证</span>');
-    return '<div>'+it.t+' · '+ (it.mc_name) + s +'</div>'}).join('')})}
+  box.textContent='';
+  j.items.forEach(function(it){
+    var d=document.createElement('div');
+    d.appendChild(document.createTextNode(String(it.t||'')+' · '));
+    d.appendChild(document.createTextNode(String(it.mc_name||'')));   // 文本节点：不会被解析为 HTML
+    var s=document.createElement('span');
+    s.className=it.submitted_at?'pill p-ok':(it.expired?'pill p-bad':'pill p-wait');
+    s.textContent=it.submitted_at?'已通过':(it.expired?'已过期':'待验证');
+    d.appendChild(s);
+    box.appendChild(d);
+  })})}
```

## 为什么能堵住复现路径
- 原路径：`mc_name` 未经转义进入 `innerHTML`，浏览器把 `<img onerror=...>` 解析为元素并执行；
- 改后：`createTextNode` / `textContent` 把同一字符串作为**文本**插入，`<` 被当作字符而非标签，任何 MC 名（含 `<script>`、`<img>`、`"`）都不可能形成元素或属性；
- 与同文件 :381 的服务端 `htmlspecialchars` 策略一致，消除"一处转义、一处不转义"的不一致。

## 备选改法
- **B（改动更小）**：保留 `innerHTML`，但先 `escapeHtml(it.mc_name)`：
  ```js
  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
  return '<div>'+esc(it.t)+' · '+esc(it.mc_name)+s+'</div>';
  ```
  需要保证所有插值都过 `esc`，维护成本高于 A。
- **C（纵深防御）**：同时给 mcverify 加 CSP（见 WEB-13 修复），即使将来再出现一处拼接，脚本也无法执行。

## 兼容/迁移风险
- 纯前端渲染改动，不涉及接口字段；旧浏览器（`createTextNode`）全支持；
- 若线上 MC 名都来自原版 Bukkit（`[A-Za-z0-9_]`），本缺陷暂无实际触发路径，但 `mc-api.php:45` 仅限长度、且第三方代理/Bungee/Velocity 可放宽字符集，故仍应按"不可信输入"处理。

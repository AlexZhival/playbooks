/* A-Players · Предиктивные модели — вход по логину/паролю.
   СМЕНИ ЛОГИН/ПАРОЛЬ В СЛЕДУЮЩЕЙ СТРОКЕ ↓ (это единственное место). */
(function () {
  var USER = "a-players", PASS = "Modeli-2026";   // ← логин и пароль сюда
  var OK = "apx_pm_ok";
  var authed = false;
  try { authed = sessionStorage.getItem(OK) === "1"; } catch (e) {}

  if (!authed) { try { document.documentElement.style.visibility = "hidden"; } catch (e) {} }

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    try { document.documentElement.style.visibility = ""; } catch (e) {}
    if (authed) return;

    var d = document.createElement("div");
    d.setAttribute("style", "position:fixed;inset:0;z-index:99999;background:#12372A;display:flex;align-items:center;justify-content:center;font-family:-apple-system,Segoe UI,Roboto,sans-serif");
    d.innerHTML =
      '<div style="background:#FBF8F1;border-radius:16px;padding:30px 28px;width:330px;max-width:90vw;box-shadow:0 20px 60px rgba(0,0,0,.4);text-align:center">' +
      '<div style="font-weight:800;color:#12372A;font-size:19px">A-PLAYERS</div>' +
      '<div style="color:#6B756F;font-size:13.5px;margin:4px 0 18px">Модуль «Предиктивные модели». Вход по логину и паролю.</div>' +
      '<input id="_gu" placeholder="Логин" autocomplete="username" style="width:100%;padding:11px 13px;border:1px solid #E7E0D2;border-radius:9px;margin-bottom:9px;font-size:15px;box-sizing:border-box">' +
      '<input id="_gp" type="password" placeholder="Пароль" autocomplete="current-password" style="width:100%;padding:11px 13px;border:1px solid #E7E0D2;border-radius:9px;margin-bottom:14px;font-size:15px;box-sizing:border-box">' +
      '<button id="_gb" style="width:100%;background:#12372A;color:#fff;border:none;border-radius:9px;padding:12px;font-weight:700;font-size:15px;cursor:pointer">Войти</button>' +
      '<div id="_ge" style="color:#b4472a;font-size:13px;margin-top:9px;min-height:16px"></div></div>';
    document.body.appendChild(d);
    document.documentElement.style.overflow = "hidden";

    function go() {
      var u = document.getElementById("_gu").value.trim().toLowerCase();
      var p = document.getElementById("_gp").value;
      if (u === USER.toLowerCase() && p === PASS) {
        try { sessionStorage.setItem(OK, "1"); } catch (e) {}
        d.remove();
        document.documentElement.style.overflow = "";
      } else {
        document.getElementById("_ge").textContent = "Неверный логин или пароль";
      }
    }
    document.getElementById("_gb").onclick = go;
    document.getElementById("_gp").addEventListener("keydown", function (e) { if (e.key === "Enter") go(); });
    document.getElementById("_gu").focus();
  });
})();

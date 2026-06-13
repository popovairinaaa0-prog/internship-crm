// Подкрашивает строки таблицы студентов фоном по сроку контакта.
// Дёрнем по DOMContentLoaded и продублируем для возможной AJAX-перерисовки.
(function () {
    function tintRowsByContactDate() {
        document.querySelectorAll("table tbody tr").forEach(function (tr) {
            if (tr.querySelector(".contact-date--overdue")) {
                tr.classList.add("row-overdue");
            } else if (tr.querySelector(".contact-date--today")) {
                tr.classList.add("row-today");
            } else if (tr.querySelector(".contact-date--soon")) {
                tr.classList.add("row-soon");
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", tintRowsByContactDate);
    } else {
        tintRowsByContactDate();
    }
})();

// Звёздное небо: добавляем фоновый слой со звёздами сразу после body.
// На светлой теме слой скрыт через CSS.
(function () {
    function inject() {
        if (document.getElementById("zero-stars")) return;
        var stars = document.createElement("div");
        stars.id = "zero-stars";
        document.body.appendChild(stars);
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", inject);
    } else {
        inject();
    }
})();

// Зелёный glow-курсор: плавно догоняет мышку, мягкое сияние позади неё.
(function () {
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        return; // Уважаем системную настройку «меньше анимации»
    }
    if (window.matchMedia && window.matchMedia("(pointer: coarse)").matches) {
        return; // На тач-устройствах смысла нет
    }

    function init() {
        if (document.querySelector(".cursor-glow")) return;
        var glow = document.createElement("div");
        glow.className = "cursor-glow";
        document.body.appendChild(glow);

        var targetX = window.innerWidth / 2;
        var targetY = window.innerHeight / 2;
        var x = targetX;
        var y = targetY;
        var visible = false;

        document.addEventListener("mousemove", function (e) {
            targetX = e.clientX;
            targetY = e.clientY;
            if (!visible) {
                visible = true;
                glow.classList.add("is-visible");
            }
        });
        document.addEventListener("mouseleave", function () {
            visible = false;
            glow.classList.remove("is-visible");
        });

        function tick() {
            // Лёгкая инерция — glow плавно догоняет мышку
            x += (targetX - x) * 0.18;
            y += (targetY - y) * 0.18;
            glow.style.transform = "translate(" + (x - 55) + "px," + (y - 55) + "px)";
            requestAnimationFrame(tick);
        }
        tick();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();

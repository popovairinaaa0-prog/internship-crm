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

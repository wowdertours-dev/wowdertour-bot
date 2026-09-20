(() => {
    "use strict";

    function normalizeText(value) {
        return (value || "")
            .replace(/\s+/g, " ")
            .trim()
            .toLowerCase();
    }

    function findOpenLinks() {
        return Array.from(
            document.querySelectorAll('a[href]')
        ).filter((link) => {
            const text = normalizeText(
                link.textContent
            );

            return (
                text === "открыть"
                && link.getAttribute("href")
            );
        });
    }

    function findCard(link) {
        return (
            link.closest(".booking-summary")
            || link.closest(".booking-card")
            || link.closest(".booking-row")
            || link.closest("article")
            || link.closest("li")
            || link.parentElement
        );
    }

    function isInteractiveTarget(target) {
        return Boolean(
            target.closest(
                [
                    "a",
                    "button",
                    "input",
                    "select",
                    "textarea",
                    "label",
                    "form",
                    "details",
                    "summary"
                ].join(",")
            )
        );
    }

    function makeClickable(link) {
        const href = link.getAttribute("href");
        const card = findCard(link);

        if (
            !href
            || !card
            || card.dataset.bookingClickable === "1"
        ) {
            return;
        }

        card.dataset.bookingClickable = "1";
        card.classList.add(
            "booking-clickable-row"
        );

        card.setAttribute(
            "role",
            "link"
        );

        card.setAttribute(
            "tabindex",
            "0"
        );

        card.setAttribute(
            "aria-label",
            "Открыть заявку"
        );

        // Кнопка больше не нужна:
        // вся строка теперь является ссылкой.
        link.style.display = "none";

        card.addEventListener(
            "click",
            (event) => {
                if (
                    isInteractiveTarget(
                        event.target
                    )
                ) {
                    return;
                }

                window.location.href = href;
            }
        );

        card.addEventListener(
            "keydown",
            (event) => {
                if (
                    event.key === "Enter"
                    || event.key === " "
                ) {
                    event.preventDefault();
                    window.location.href = href;
                }
            }
        );
    }

    function init() {
        findOpenLinks().forEach(
            makeClickable
        );
    }

    if (
        document.readyState
        === "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            init
        );
    } else {
        init();
    }
})();

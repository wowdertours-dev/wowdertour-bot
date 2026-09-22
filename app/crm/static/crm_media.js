(() => {
    "use strict";

    const MEDIA_ID_RE = /\/media\/(\d+)\/(?:delete|toggle|move)$/;

    function getMediaId(card) {
        const forms = card.querySelectorAll("form[action]");

        for (const form of forms) {
            const action = form.getAttribute("action") || "";
            const match = action.match(MEDIA_ID_RE);

            if (match) {
                return Number(match[1]);
            }
        }

        return null;
    }

    function enhanceUploadForm(form) {
        const input = form.querySelector('input[type="file"]');

        if (!input || form.dataset.dndReady === "1") {
            return;
        }

        form.dataset.dndReady = "1";
        form.classList.add("media-dnd-ready");

        input.multiple = true;
        input.name = "photos";

        const content = document.createElement("div");
        content.className = "media-dropzone-content";

        content.innerHTML = `
            <div class="media-dropzone-icon">📸</div>
            <div class="media-dropzone-title">
                Перетащи фотографии сюда
            </div>
            <div class="media-dropzone-subtitle">
                или нажми, чтобы выбрать несколько файлов.
                До 5 фото за раз, до 10 МБ каждое и до 20 МБ суммарно.
            </div>
            <div class="media-dropzone-status"></div>
        `;

        form.appendChild(content);

        const status = content.querySelector(
            ".media-dropzone-status"
        );

        form.addEventListener("submit", (event) => {
            const files = Array.from(input.files || []);
            let error = "";
            if (!files.length) error = "Выбери хотя бы одно фото.";
            else if (files.some(file => !file.type.startsWith("image/")))
                error = "Можно загружать только изображения.";
            else if (files.length > 5) error = "За один раз можно загрузить не больше 5 фото.";
            else if (files.some(file => file.size > 10 * 1024 * 1024))
                error = "Фото должно быть не больше 10 МБ.";
            else if (files.reduce((sum, file) => sum + file.size, 0) > 20 * 1024 * 1024)
                error = "Общий размер фотографий должен быть не больше 20 МБ.";
            if (error) {
                event.preventDefault();
                status.textContent = error;
                form.classList.remove("is-uploading");
                return;
            }
            status.textContent = `Загружаем: ${files.length} фото…`;
            form.classList.add("is-uploading");
        });

        function submitFiles() {
            if (input.files && input.files.length) form.requestSubmit();
        }

        form.addEventListener("click", (event) => {
            if (
                event.target.closest("button") ||
                event.target === input
            ) {
                return;
            }

            input.click();
        });

        input.addEventListener("change", submitFiles);

        form.addEventListener("dragenter", (event) => {
            event.preventDefault();
            form.classList.add("is-dragover");
        });

        form.addEventListener("dragover", (event) => {
            event.preventDefault();
            form.classList.add("is-dragover");
        });

        form.addEventListener("dragleave", (event) => {
            if (!form.contains(event.relatedTarget)) {
                form.classList.remove("is-dragover");
            }
        });

        form.addEventListener("drop", (event) => {
            event.preventDefault();
            form.classList.remove("is-dragover");

            const files = Array.from(
                event.dataTransfer?.files || []
            ).filter(
                (file) => file.type.startsWith("image/")
            );

            if (files.length === 0) {
                status.textContent =
                    "Перетащи сюда изображения.";
                return;
            }

            const transfer = new DataTransfer();

            files.forEach((file) => {
                transfer.items.add(file);
            });

            input.files = transfer.files;

            submitFiles();
        });
    }

    async function saveOrder(grid, status) {
        const ids = Array.from(
            grid.querySelectorAll(".media-card")
        )
            .map(getMediaId)
            .filter((value) => Number.isInteger(value));

        if (ids.length < 2) {
            return;
        }

        status.className =
            "media-sort-status is-saving";
        status.textContent =
            "Сохраняем порядок…";

        try {
            const response = await fetch(
                "/media/reorder",
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json",
                    },
                    body: JSON.stringify({
                        media_ids: ids,
                    }),
                }
            );

            const data = await response.json();

            if (!response.ok || !data.ok) {
                throw new Error(
                    data.error ||
                    "Не удалось сохранить порядок"
                );
            }

            status.className =
                "media-sort-status is-success";
            status.textContent =
                "Порядок сохранён";

            window.setTimeout(() => {
                status.textContent = "";
                status.className =
                    "media-sort-status";
            }, 1600);
        } catch (error) {
            status.className =
                "media-sort-status is-error";
            status.textContent =
                error.message ||
                "Ошибка сохранения порядка";
        }
    }

    function enhanceGrid(grid) {
        if (grid.dataset.sortReady === "1") {
            return;
        }

        const cards = Array.from(
            grid.querySelectorAll(".media-card")
        ).filter(
            (card) => getMediaId(card) !== null
        );

        if (cards.length === 0) {
            return;
        }

        grid.dataset.sortReady = "1";
        grid.classList.add("media-sort-ready");

        const status = document.createElement("div");
        status.className = "media-sort-status";
        grid.insertAdjacentElement(
            "afterend",
            status
        );

        let draggedCard = null;
        let draggedHandle = null;
        let startOrder = "";
        let pointerId = null;

        function orderKey() {
            return Array.from(
                grid.querySelectorAll(".media-card")
            )
                .map(getMediaId)
                .filter((id) => id !== null)
                .join(",");
        }

        cards.forEach((card) => {
            const handle = document.createElement("div");
            handle.className = "media-drag-handle";
            handle.innerHTML =
                '<span>↕</span><span>Перетащи, чтобы изменить порядок</span>';

            const name = card.querySelector(".media-name");

            if (name) {
                name.insertAdjacentElement(
                    "afterend",
                    handle
                );
            } else {
                card.prepend(handle);
            }

            handle.addEventListener(
                "pointerdown",
                (event) => {
                    if (event.button !== undefined && event.button !== 0) {
                        return;
                    }

                    draggedCard = card;
                    draggedHandle = handle;
                    pointerId = event.pointerId;
                    startOrder = orderKey();

                    handle.setPointerCapture(
                        event.pointerId
                    );

                    card.classList.add(
                        "is-sorting"
                    );

                    event.preventDefault();
                }
            );

            handle.addEventListener(
                "pointermove",
                (event) => {
                    if (
                        !draggedCard ||
                        pointerId !== event.pointerId
                    ) {
                        return;
                    }

                    const underPointer =
                        document.elementFromPoint(
                            event.clientX,
                            event.clientY
                        );

                    const target =
                        underPointer?.closest(
                            ".media-card"
                        );

                    if (
                        !target ||
                        target === draggedCard ||
                        target.parentElement !== grid
                    ) {
                        return;
                    }

                    const rect =
                        target.getBoundingClientRect();

                    const horizontal =
                        Math.abs(
                            event.clientX -
                            (rect.left + rect.width / 2)
                        );

                    const vertical =
                        Math.abs(
                            event.clientY -
                            (rect.top + rect.height / 2)
                        );

                    let insertAfter;

                    if (horizontal > vertical) {
                        insertAfter =
                            event.clientX >
                            rect.left + rect.width / 2;
                    } else {
                        insertAfter =
                            event.clientY >
                            rect.top + rect.height / 2;
                    }

                    if (insertAfter) {
                        target.insertAdjacentElement(
                            "afterend",
                            draggedCard
                        );
                    } else {
                        target.insertAdjacentElement(
                            "beforebegin",
                            draggedCard
                        );
                    }
                }
            );

            async function finish(event) {
                if (
                    !draggedCard ||
                    pointerId !== event.pointerId
                ) {
                    return;
                }

                try {
                    if (
                        draggedHandle?.hasPointerCapture(
                            event.pointerId
                        )
                    ) {
                        draggedHandle.releasePointerCapture(
                            event.pointerId
                        );
                    }
                } catch (_) {
                    // no-op
                }

                draggedCard.classList.remove(
                    "is-sorting"
                );

                const changed =
                    startOrder !== orderKey();

                draggedCard = null;
                draggedHandle = null;
                pointerId = null;

                if (changed) {
                    await saveOrder(
                        grid,
                        status
                    );
                }
            }

            handle.addEventListener(
                "pointerup",
                finish
            );

            handle.addEventListener(
                "pointercancel",
                finish
            );
        });
    }

    function init() {
        document
            .querySelectorAll(".media-upload-form")
            .forEach(enhanceUploadForm);

        document
            .querySelectorAll(".media-grid")
            .forEach(enhanceGrid);
    }

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            init
        );
    } else {
        init();
    }
})();

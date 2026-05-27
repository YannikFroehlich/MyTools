document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('id_avatar');
    const croppedInput = document.getElementById('avatar-cropped-input');
    const modal = document.getElementById('avatar-crop-modal');
    const cropArea = document.getElementById('avatar-crop-area');
    const cropImage = document.getElementById('avatar-crop-image');
    const zoomRange = document.getElementById('avatar-zoom-range');
    const applyButton = document.getElementById('avatar-crop-apply');
    const livePreview = document.getElementById('profile-avatar-live-preview');

    if (!fileInput || !croppedInput || !modal || !cropArea || !cropImage || !zoomRange || !applyButton) {
        return;
    }

    let imageLoaded = false;
    let imageNaturalWidth = 0;
    let imageNaturalHeight = 0;

    let baseScale = 1;
    let zoom = 1;
    let offsetX = 0;
    let offsetY = 0;

    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;
    let dragStartOffsetX = 0;
    let dragStartOffsetY = 0;

    function openModal() {
        modal.classList.add('open');
        modal.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        modal.classList.remove('open');
        modal.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
    }

    function cropSize() {
        return cropArea.clientWidth * 0.68;
    }

    function currentScale() {
        return baseScale * zoom;
    }

    function clampOffsets() {
        const areaWidth = cropArea.clientWidth;
        const areaHeight = cropArea.clientHeight;
        const circleSize = cropSize();

        const scaledWidth = imageNaturalWidth * currentScale();
        const scaledHeight = imageNaturalHeight * currentScale();

        const maxOffsetX = Math.max(0, (scaledWidth - circleSize) / 2);
        const maxOffsetY = Math.max(0, (scaledHeight - circleSize) / 2);

        offsetX = Math.min(maxOffsetX, Math.max(-maxOffsetX, offsetX));
        offsetY = Math.min(maxOffsetY, Math.max(-maxOffsetY, offsetY));

        if (scaledWidth < circleSize) {
            offsetX = 0;
        }

        if (scaledHeight < circleSize) {
            offsetY = 0;
        }
    }

    function updateImageTransform() {
        if (!imageLoaded) {
            return;
        }

        clampOffsets();

        cropImage.style.width = `${imageNaturalWidth}px`;
        cropImage.style.height = `${imageNaturalHeight}px`;
        cropImage.style.transform = `translate(calc(-50% + ${offsetX}px), calc(-50% + ${offsetY}px)) scale(${currentScale()})`;
    }

    function resetCropState() {
        const areaWidth = cropArea.clientWidth;
        const areaHeight = cropArea.clientHeight;
        const circleSize = cropSize();

        baseScale = Math.max(
            circleSize / imageNaturalWidth,
            circleSize / imageNaturalHeight
        );

        zoom = 1;
        offsetX = 0;
        offsetY = 0;

        zoomRange.value = '1';

        cropImage.style.left = `${areaWidth / 2}px`;
        cropImage.style.top = `${areaHeight / 2}px`;

        updateImageTransform();
    }

    function getPointerPosition(event) {
        if (event.touches && event.touches.length > 0) {
            return {
                x: event.touches[0].clientX,
                y: event.touches[0].clientY,
            };
        }

        return {
            x: event.clientX,
            y: event.clientY,
        };
    }

    fileInput.addEventListener('change', () => {
        const file = fileInput.files && fileInput.files[0];

        if (!file) {
            return;
        }

        if (!file.type.startsWith('image/')) {
            fileInput.value = '';
            return;
        }

        const reader = new FileReader();

        reader.onload = (event) => {
            cropImage.onload = () => {
                imageLoaded = true;
                imageNaturalWidth = cropImage.naturalWidth;
                imageNaturalHeight = cropImage.naturalHeight;

                openModal();

                requestAnimationFrame(() => {
                    resetCropState();
                });
            };

            cropImage.src = event.target.result;
        };

        reader.readAsDataURL(file);
    });

    zoomRange.addEventListener('input', () => {
        zoom = Number(zoomRange.value);
        updateImageTransform();
    });

    cropArea.addEventListener('mousedown', (event) => {
        if (!imageLoaded) {
            return;
        }

        isDragging = true;
        const position = getPointerPosition(event);

        dragStartX = position.x;
        dragStartY = position.y;
        dragStartOffsetX = offsetX;
        dragStartOffsetY = offsetY;
    });

    window.addEventListener('mousemove', (event) => {
        if (!isDragging) {
            return;
        }

        const position = getPointerPosition(event);

        offsetX = dragStartOffsetX + (position.x - dragStartX);
        offsetY = dragStartOffsetY + (position.y - dragStartY);

        updateImageTransform();
    });

    window.addEventListener('mouseup', () => {
        isDragging = false;
    });

    cropArea.addEventListener('touchstart', (event) => {
        if (!imageLoaded) {
            return;
        }

        event.preventDefault();

        isDragging = true;
        const position = getPointerPosition(event);

        dragStartX = position.x;
        dragStartY = position.y;
        dragStartOffsetX = offsetX;
        dragStartOffsetY = offsetY;
    }, { passive: false });

    window.addEventListener('touchmove', (event) => {
        if (!isDragging) {
            return;
        }

        event.preventDefault();

        const position = getPointerPosition(event);

        offsetX = dragStartOffsetX + (position.x - dragStartX);
        offsetY = dragStartOffsetY + (position.y - dragStartY);

        updateImageTransform();
    }, { passive: false });

    window.addEventListener('touchend', () => {
        isDragging = false;
    });

    cropArea.addEventListener('wheel', (event) => {
        if (!imageLoaded) {
            return;
        }

        event.preventDefault();

        const direction = event.deltaY > 0 ? -0.05 : 0.05;
        const nextZoom = Math.min(3, Math.max(1, zoom + direction));

        zoom = nextZoom;
        zoomRange.value = String(nextZoom);
        updateImageTransform();
    }, { passive: false });

    applyButton.addEventListener('click', () => {
        if (!imageLoaded) {
            return;
        }

        const outputSize = 512;
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');

        canvas.width = outputSize;
        canvas.height = outputSize;

        context.clearRect(0, 0, outputSize, outputSize);

        const squareSize = cropSize();
        const scaleToOutput = outputSize / squareSize;

        const drawnWidth = imageNaturalWidth * currentScale() * scaleToOutput;
        const drawnHeight = imageNaturalHeight * currentScale() * scaleToOutput;

        const drawX = (outputSize - drawnWidth) / 2 + offsetX * scaleToOutput;
        const drawY = (outputSize - drawnHeight) / 2 + offsetY * scaleToOutput;

        context.drawImage(cropImage, drawX, drawY, drawnWidth, drawnHeight);

        const dataUrl = canvas.toDataURL('image/png', 0.95);
        croppedInput.value = dataUrl;

        if (livePreview) {
            livePreview.innerHTML = '';
            const img = document.createElement('img');
            img.src = dataUrl;
            img.alt = 'Profilbild Vorschau';
            livePreview.appendChild(img);
        }

        closeModal();
    });

    document.querySelectorAll('[data-avatar-crop-close]').forEach((button) => {
        button.addEventListener('click', () => {
            closeModal();
        });
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && modal.classList.contains('open')) {
            closeModal();
        }
    });

    window.addEventListener('resize', () => {
        if (modal.classList.contains('open') && imageLoaded) {
            resetCropState();
        }
    });
});
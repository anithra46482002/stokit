const MAX_DIMENSION = 2560;
const TARGET_BYTES = 2 * 1024 * 1024;
const MIN_QUALITY = 0.48;

function canvasToWebp(canvas, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob || blob.type !== 'image/webp') {
        reject(new Error('This browser could not convert the image to WebP. Try a recent version of Chrome or Edge.'));
        return;
      }
      resolve(blob);
    }, 'image/webp', quality);
  });
}

export async function compressImageToWebp(file) {
  if (!(file instanceof Blob) || !file.type.startsWith('image/')) {
    throw new Error('Choose a valid image file.');
  }
  const bitmap = await createImageBitmap(file);
  try {
    const scale = Math.min(1, MAX_DIMENSION / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext('2d');
    if (!context) throw new Error('Image compression is unavailable in this browser.');
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);

    let quality = 0.84;
    let result = await canvasToWebp(canvas, quality);
    while (result.size > TARGET_BYTES && quality > MIN_QUALITY) {
      quality = Math.max(MIN_QUALITY, quality - 0.1);
      result = await canvasToWebp(canvas, quality);
    }
    const baseName = String(file.name || 'image').replace(/\.[^.]+$/, '') || 'image';
    return new File([result], baseName + '.webp', { type: 'image/webp', lastModified: Date.now() });
  } finally {
    bitmap.close?.();
  }
}
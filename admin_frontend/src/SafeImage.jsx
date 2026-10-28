import React from 'react';
import { imageDisplayState, mediaBaseFromApiBase } from './imageUrl';

const MEDIA_BASE = import.meta.env.VITE_MEDIA_BASE_URL
  || mediaBaseFromApiBase(import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/admin-api/');

// <img> that resolves relative paths against the media base, and shows one neutral placeholder instead of a
// broken-image icon when the value is missing/unusable or the request fails. A failed URL is remembered so the
// browser never retries it in a loop; the state resets automatically when `src` changes (e.g. after an upload).
export default function SafeImage({ src, alt = '', className = '', fallback = '-', ...rest }) {
  const [failedSrc, setFailedSrc] = React.useState('');
  const { kind, url: resolved } = imageDisplayState(src, failedSrc, MEDIA_BASE);
  if (kind === 'fallback') {
    return <span className={className + ' sk-img-fallback'} role="img" aria-label={alt ? alt + ' (image unavailable)' : 'Image unavailable'}>{fallback}</span>;
  }
  return <img className={className} src={resolved} alt={alt} loading="lazy" onError={() => setFailedSrc(resolved)} {...rest} />;
}

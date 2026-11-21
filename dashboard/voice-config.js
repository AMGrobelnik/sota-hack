/* Settings for voice.js, which loads this file from its own folder.
 *
 * endpoint: base address of a public ChipIn transcription server, for
 *   example "https://voice.example.org". voice.js posts each spoken phrase
 *   to <endpoint>/api/transcribe once <endpoint>/api/health says
 *   transcription is available. Leave it empty to keep the browser's own
 *   speech recognition. A ChipIn backend connected on this computer is
 *   always preferred over this endpoint. Never put a key or token here:
 *   this file is public.
 * preview: false turns off the browser's live preview words while the
 *   server engine is listening.
 */
window.CHIPIN_VOICE = window.CHIPIN_VOICE || { endpoint: "" };

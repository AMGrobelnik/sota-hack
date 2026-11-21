// The waitlist store. Paste its URL here; empty keeps the count hidden and the join form closed.
// GET  endpoint -> {"count": N}
// POST endpoint with JSON {name, email, organisation, build, variant} -> {"ok": true, "count": N}
window.WAITLIST = { endpoint: "https://sota-hack-waitlist.amgrobelnik.workers.dev/" };

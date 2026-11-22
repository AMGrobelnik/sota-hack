// The waitlist store. Paste its URL here; empty keeps the count hidden and the join form closed.
// GET  endpoint -> {"count": N, "countries": [{"code": "GB", "count": 212}, ...]}   (countries optional)
// POST endpoint with JSON {name, email, organisation, build, variant} -> {"ok": true, "count": N}
//
// MOCK NUMBERS (preview only). While the block below is present, the pages show this made-up count
// and these made-up countries instead of asking the store. Sign-ups through the form still go to the
// real store. DELETE THE WHOLE `mock: { ... }` BLOCK to switch every page to the real numbers.
window.WAITLIST = {
  endpoint: "https://sota-hack-waitlist.amgrobelnik.workers.dev/",
  mock: {
    count: 30,
    countries: [
      { code: "GB", count: 9 }, { code: "US", count: 5 }, { code: "DE", count: 3 },
      { code: "FR", count: 3 }, { code: "NL", count: 2 }, { code: "CH", count: 2 },
      { code: "SI", count: 2 }, { code: "IN", count: 2 }, { code: "SG", count: 2 }
    ]
  }
};

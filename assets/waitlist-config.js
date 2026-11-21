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
    count: 1284,
    countries: [
      { code: "GB", count: 212 }, { code: "US", count: 186 }, { code: "DE", count: 118 },
      { code: "FR", count: 96 }, { code: "NL", count: 84 }, { code: "CH", count: 71 },
      { code: "SI", count: 64 }, { code: "RO", count: 58 }, { code: "IL", count: 52 },
      { code: "IN", count: 49 }, { code: "SG", count: 41 }, { code: "CA", count: 38 },
      { code: "AU", count: 33 }, { code: "ES", count: 30 }, { code: "IT", count: 28 },
      { code: "SE", count: 24 }, { code: "PL", count: 22 }, { code: "IE", count: 20 },
      { code: "PT", count: 17 }, { code: "JP", count: 15 }, { code: "BR", count: 13 },
      { code: "ZA", count: 6 }, { code: "NG", count: 4 }, { code: "AE", count: 3 }
    ]
  }
};

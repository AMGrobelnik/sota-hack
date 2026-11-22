# Waitlist count and world map

Files (all in `assets/`): `waitlist-config.js`, `waitlist.js`, `waitlist-world.js`,
`waitlist-map.js`. Pages in `variants/` load them as `../assets/...`.

## Script tags, in this order (before `</body>`)

```html
<script src="../assets/waitlist-config.js"></script>
<script src="../assets/waitlist.js"></script>
<script src="../assets/waitlist-world.js"></script>
<script src="../assets/waitlist-map.js"></script>
```

Pages that only want the count can stop after `waitlist.js`.

## Count line

```html
<p class="wl" data-waitlist-wrap hidden><span data-waitlist-count></span></p>
```

Shows "30 people on the waitlist". The wrapper starts `hidden` and is shown once a number
is known (never shown for 0). Style the wrapper however the page needs.

## Map

```html
<div data-waitlist-map></div>
```

Filled with an inline SVG (width 100 percent, height follows) and the legend "People from 9
countries". Give the div the width you want (for example a max-width container); it redraws
when that width changes. Any number of maps and count lines per page.

Colours, set in the page's CSS on the div or any ancestor:

- `--wl-accent`: sign-up countries, dots and pulse (default `#2f6bff`).
- `--wl-land`: fill of all other countries (default: the text colour at 14 percent, so it
  suits light and dark pages alike). Outlines also follow the text colour.

The legend takes the font and colour of the surrounding text; restyle it with `.wlm-legend`.
Motion stops under `prefers-reduced-motion`.

## Mock numbers

`waitlist-config.js` has a `mock: { count, countries }` block. While it is there, pages show
those made-up numbers and make no request for the count (the join form still posts to the real
store). Delete the whole `mock` block to switch to the real numbers: the store's GET reply is
then used, `{"count": N, "countries": [{"code": "GB", "count": 212}, ...]}`; without
`countries` the map shows no highlighted countries.

## Map data

`waitlist-world.js` (about 120 KB): Natural Earth 1:110m countries, public domain
(naturalearthdata.com), from the world-atlas TopoJSON, pre-projected. Countries too small for
110m (for example Singapore) get a dot but no shape. No request is made at run time.

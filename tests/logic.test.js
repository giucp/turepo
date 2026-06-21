// Tests de la lógica crítica de Tu Repo.
// Carga el <script> REAL de index.html en un sandbox (navegador simulado) y
// prueba las funciones puras que NO pueden romperse al editar con IA:
//   - niveles por puntos (nivelIdx / nivelDe)
//   - formato del dólar (fxFmt)
//   - filtro de groserías / caracteres raros (textoNoPermitido)
//   - severidad de un reporte (sevDe)
//
// No necesita dependencias. Correr:  node tests/logic.test.js
// Sale con código !=0 si algo falla (sirve para CI o un pre-commit).

const fs = require('fs');
const vm = require('vm');
const path = require('path');

function loadApp() {
  const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
  const blocks = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)].map(m => m[1]);
  const code = blocks.sort((a, b) => b.length - a.length)[0]; // el bloque grande = la app

  // Mock universal del navegador: cualquier acceso/llamada devuelve el mismo stub.
  const stub = new Proxy(function () { return stub; }, {
    get(t, p) {
      if (p === 'length') return 0;
      if (p === Symbol.toPrimitive) return () => '';
      if (p === 'then') return undefined; // que no sea "thenable"
      return stub;
    },
    apply() { return stub; },
    construct() { return stub; },
  });

  const sb = {
    document: stub, localStorage: stub, navigator: stub, history: stub, supabase: stub,
    location: { search: '', href: '', hash: '', reload() {} },
    matchMedia: () => stub,
    setTimeout() {}, setInterval() {}, clearTimeout() {}, clearInterval() {}, requestAnimationFrame() {},
    fetch: () => new Promise(() => {}), // nunca resuelve -> sin logs async del arranque
    URLSearchParams, addEventListener() {}, removeEventListener() {},
    console: { log() {}, warn() {}, error() {}, info() {} }, // silenciar ruido del arranque
  };
  sb.window = sb; sb.globalThis = sb; sb.self = sb;
  vm.createContext(sb);
  vm.runInContext(code, sb, { timeout: 8000 });
  return sb;
}

// ---- mini framework de asserts (sin dependencias) ----
let pass = 0; const fails = [];
function eq(actual, expected, msg) {
  if (actual === expected) { pass++; }
  else fails.push(`${msg}\n    esperado: ${JSON.stringify(expected)}\n    obtenido: ${JSON.stringify(actual)}`);
}
function ok(cond, msg) { eq(!!cond, true, msg); }

const app = loadApp();

// ============ Niveles por puntos ============
// Umbrales: 0 / 50 / 150 / 400 / 1000  ->  índices 0..4
eq(app.nivelIdx(0),    0, 'nivelIdx(0)');
eq(app.nivelIdx(49),   0, 'nivelIdx(49)');
eq(app.nivelIdx(50),   1, 'nivelIdx(50)');
eq(app.nivelIdx(149),  1, 'nivelIdx(149)');
eq(app.nivelIdx(150),  2, 'nivelIdx(150)');
eq(app.nivelIdx(399),  2, 'nivelIdx(399)');
eq(app.nivelIdx(400),  3, 'nivelIdx(400)');
eq(app.nivelIdx(999),  3, 'nivelIdx(999)');
eq(app.nivelIdx(1000), 4, 'nivelIdx(1000)');
eq(app.nivelIdx(99999),4, 'nivelIdx(99999)');
eq(app.nivelIdx(null), 0, 'nivelIdx(null) no rompe');
eq(app.nivelDe(50).n, 'Vecino', 'nivelDe(50).n');
eq(app.nivelDe(1000).n,'Leyenda','nivelDe(1000).n');

// ============ Formato del dólar (es-VE: miles "." decimales ",") ============
eq(app.fxFmt(612.4),    'Bs. 612,40',   'fxFmt(612.4)');
eq(app.fxFmt(0),        'Bs. 0,00',     'fxFmt(0)');
eq(app.fxFmt(1234.5),   'Bs. 1.234,50', 'fxFmt(1234.5)');
eq(app.fxFmt(1000000),  'Bs. 1.000.000,00', 'fxFmt(1000000)');

// ============ Filtro de groserías / caracteres ============
// Texto limpio -> permitido
eq(app.textoNoPermitido('hola vecino, se fue la luz'), false, 'limpio no se bloquea');
eq(app.textoNoPermitido('llego la gasolina en la bomba'), false, 'limpio 2 no se bloquea');
// Lugares legítimos NO deben bloquearse (coincidencia por palabra completa)
eq(app.textoNoPermitido('Maracay'),  false, 'Maracay permitido');
eq(app.textoNoPermitido('Maracaibo'),false, 'Maracaibo permitido');
// Groserías / política -> bloqueadas
ok(app.textoNoPermitido('maduro'),        'bloquea politica');
ok(app.textoNoPermitido('eres un coño'),  'bloquea groseria');
// Trucos de ofuscación -> también bloqueadas (los neutraliza normalizar())
ok(app.textoNoPermitido('m4dur0'),  'bloquea m4dur0');
ok(app.textoNoPermitido('c0ño'),    'bloquea c0ño');
ok(app.textoNoPermitido('$hit'),    'bloquea $hit');
ok(app.textoNoPermitido('FUCK'),    'bloquea mayusculas');
// Caracteres raros / exceso de emojis
ok(app.textoNoPermitido('hola <script>'), 'bloquea caracteres raros');
ok(app.textoNoPermitido('hola 😀😀😀'),    'bloquea >2 emojis');
eq(app.textoNoPermitido('todo bien 😀'), false, 'permite 1 emoji');

// ============ Severidad de un reporte ============
eq(app.sevDe({ estado: 'sin_luz' }),  'bad',  'sevDe sin_luz');
eq(app.sevDe({ estado: 'robo' }),     'bad',  'sevDe robo');
eq(app.sevDe({ estado: 'con_luz' }),  'ok',   'sevDe con_luz');
eq(app.sevDe({ estado: 'bajones' }),  'warn', 'sevDe bajones');
eq(app.sevDe({ estado: 'otro' }),     'warn', 'sevDe otro');
eq(app.sevDe({ estado: 'cerrada' }),  'mid',  'sevDe cerrada (gris)');
eq(app.sevDe({ estado: 'no_existe' }),'mid',  'sevDe desconocido');

// ---- resultado ----
if (fails.length) {
  console.error(`\n❌ ${fails.length} test(s) fallaron (${pass} ok):\n`);
  fails.forEach(f => console.error('  • ' + f));
  process.exit(1);
} else {
  console.log(`✅ Todos los tests pasaron (${pass} asserts).`);
}

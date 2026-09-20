// Webhook signature verification is the only thing between "Stripe says this
// person paid" and "anyone who can POST to a public URL says so". It is
// written by hand rather than imported, so it is tested by hand — against
// forged bodies, wrong secrets, altered timestamps and replays, not only
// against the happy path a library would also pass.
//
// Compiles the source to a temporary directory and imports that, because this
// project has no test runner and adding one to run twenty assertions would be
// a worse trade than four lines of exec.
import { createHmac } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = fileURLToPath(new URL('.', import.meta.url));
const out = mkdtempSync(join(tmpdir(), 'sigtest-'));
execFileSync('npx', ['tsc', join(here, '..', 'lib', 'stripeSignature.ts'),
                     '--outDir', out, '--module', 'esnext', '--target', 'es2022',
                     '--moduleResolution', 'bundler'],
             { stdio: 'inherit' });
const { verifyStripeSignature, TOLERANCE_SECONDS } =
  await import(join(out, 'stripeSignature.js'));

const SECRET = 'whsec_test_secret_value';
const NOW = 1_700_000_000;
const body = JSON.stringify({ id: 'evt_1', type: 'checkout.session.completed' });

const sign = (b, t, secret = SECRET) =>
  createHmac('sha256', secret).update(`${t}.${b}`, 'utf8').digest('hex');

let pass = 0, fail = 0;
const check = (label, got, want) => {
  const ok = got === want;
  ok ? pass++ : fail++;
  console.log(`  ${ok ? 'ok  ' : 'FAIL'}  ${label.padEnd(52)} ${got}`);
};

const v = (b, h, now = NOW) => verifyStripeSignature(b, h, SECRET, now).ok;

console.log('accepts what Stripe really sends');
check('valid signature', v(body, `t=${NOW},v1=${sign(body, NOW)}`), true);
check('extra v0 scheme alongside v1',
  v(body, `t=${NOW},v0=deadbeef,v1=${sign(body, NOW)}`), true);
check('two v1s, second valid (secret rotation)',
  v(body, `t=${NOW},v1=${'0'.repeat(64)},v1=${sign(body, NOW)}`), true);
check('whitespace around parts',
  v(body, ` t=${NOW} , v1=${sign(body, NOW)} `), true);
check('at the edge of tolerance',
  v(body, `t=${NOW - TOLERANCE_SECONDS},v1=${sign(body, NOW - TOLERANCE_SECONDS)}`), true);

console.log('\nrefuses forgeries');
check('no header at all', v(body, null), false);
check('empty header', v(body, ''), false);
check('signature for a DIFFERENT body',
  v(body, `t=${NOW},v1=${sign('{"id":"evt_evil"}', NOW)}`), false);
check('body altered after signing',
  v(body + ' ', `t=${NOW},v1=${sign(body, NOW)}`), false);
check('signed with the wrong secret',
  v(body, `t=${NOW},v1=${sign(body, NOW, 'whsec_attacker')}`), false);
check('timestamp changed, signature kept',
  v(body, `t=${NOW + 1},v1=${sign(body, NOW)}`), false);
check('no v1 at all', v(body, `t=${NOW},v0=${sign(body, NOW)}`), false);
check('no timestamp', v(body, `v1=${sign(body, NOW)}`), false);
check('non-numeric timestamp', v(body, `t=abc,v1=${sign(body, 'abc')}`), false);
check('truncated signature',
  v(body, `t=${NOW},v1=${sign(body, NOW).slice(0, 32)}`), false);
check('signature with trailing junk',
  v(body, `t=${NOW},v1=${sign(body, NOW)}xx`), false);

console.log('\nrefuses replays');
check('one second past tolerance',
  v(body, `t=${NOW - TOLERANCE_SECONDS - 1},v1=${sign(body, NOW - TOLERANCE_SECONDS - 1)}`), false);
check('an hour old',
  v(body, `t=${NOW - 3600},v1=${sign(body, NOW - 3600)}`), false);
check('far in the FUTURE',
  v(body, `t=${NOW + 3600},v1=${sign(body, NOW + 3600)}`), false);

console.log('\nmisconfiguration');
check('no signing secret configured',
  verifyStripeSignature(body, `t=${NOW},v1=${sign(body, NOW)}`, '', NOW).ok, false);

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);

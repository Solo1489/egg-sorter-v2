// รัน self-check และ verify แบบไม่ต้องเปิดเบราว์เซอร์:  npm run verify [-- --through=<module>]
// อ่านสเปกจาก ../3d-spec โดยตรง (อ่านอย่างเดียว) ออกด้วย exit code 1 ถ้า verify ไม่ผ่าน
import { readFile } from 'node:fs/promises';
import { checkPrograms } from '../src/animation/checkProgram.js';
import { buildMachine } from '../src/buildMachine.js';
import { BUILD_THROUGH_MODULE } from '../src/config.js';
import { checkAnimationSpec, checkPartsSpec } from '../src/selfCheck.js';
import { createSpecIndex, modulesThrough } from '../src/specIndex.js';
import { summarizeByModule, verifyMachine } from '../src/verify.js';

const specDir = new URL('../../3d-spec/', import.meta.url);
const readSpec = async (fileName) => JSON.parse(await readFile(new URL(fileName, specDir), 'utf8'));

const throughArgument = process.argv.find((argument) => argument.startsWith('--through='));
const throughModule = throughArgument ? throughArgument.split('=')[1] : BUILD_THROUGH_MODULE;

const partsSpec = await readSpec('parts.json');
const animationSpec = await readSpec('animation.json');

function printChecks(title, results) {
  console.log(`\n${title}`);
  for (const { check, ok, detail } of results) {
    console.log(`  ${ok ? '✅' : '❌'} ${check}${detail ? `  — ${detail}` : ''}`);
  }
  return results.every((result) => result.ok);
}

const isPartsSpecOk = printChecks('self-check: parts.json', checkPartsSpec(partsSpec));
const isAnimationSpecOk = printChecks(
  'self-check: animation.json',
  checkAnimationSpec(partsSpec, animationSpec),
);

if (!isPartsSpecOk) {
  console.error('\nparts.json ไม่ผ่าน self-check จึงไม่สร้างโมเดล');
  process.exit(1);
}

const { moduleOrder } = createSpecIndex(partsSpec);
const modules = modulesThrough(moduleOrder, throughModule);
const machine = buildMachine(partsSpec, { modules });
const report = verifyMachine(machine);

console.log(`\nverify: โมดูล ${modules.join(' → ')} (เกณฑ์ ${report.toleranceMm} มม.)`);
console.table(summarizeByModule(report, moduleOrder));
console.log(`กลุ่มที่สร้างแล้ว: ${[...machine.motionGroups.keys()].join(', ') || '-'}`);

if (report.skipped.length > 0) {
  console.log('ข้ามการตรวจ (ทรงกระบอกที่หมุนนอกแกนตัวเอง):');
  console.table(report.skipped.map(({ partId, pose }) => ({ partId, pose })));
}
if (!report.ok) {
  console.error('❌ verify ไม่ผ่าน:');
  console.table(report.failures.map(({ partId, pose, errorMm }) => ({ partId, pose, errorMm })));
  process.exit(1);
}
console.log(`✅ verify ผ่าน ${report.rows.length} รายการ (คลาดสูงสุด ${report.maxErrorMm.toExponential(2)} มม.)`);

if (!isAnimationSpecOk) {
  console.error('❌ animation.json ไม่ผ่าน self-check จึงไม่ตรวจแอนิเมชัน');
  process.exit(1);
}

const animationReport = checkPrograms(animationSpec, partsSpec);
console.log('\nanimation: เทียบ timeline กับทุก keyframe (ตำแหน่งไข่ / สถานะ actuator / ไฟ)');
console.table(
  animationReport.rows.map(({ problems, ...row }) => ({ ...row, failed: problems.length })),
);
if (!animationReport.ok) {
  console.error('❌ animation ไม่ผ่าน:');
  for (const row of animationReport.rows) for (const problem of row.problems) console.error(`  ${row.program}: ${problem}`);
  process.exit(1);
}
const animationChecks = animationReport.rows.reduce((sum, row) => sum + row.checks, 0);
console.log(`✅ animation ผ่าน ${animationChecks} รายการ`);

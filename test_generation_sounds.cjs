/* Transition tests; no speakers, providers or network requests. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const ts = require("./frontend/node_modules/typescript");
const source = fs.readFileSync(path.join(__dirname,"frontend/lib/generation-sounds.ts"), "utf8");
const moduleOutput = { exports: {} };
vm.runInNewContext(ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,
  {exports:moduleOutput.exports,module:moduleOutput});
const { GenerationSounds } = moduleOutput.exports;
function context() {
  const played = [], volumes = [];
  return {played, volumes, state:"running", currentTime:10, destination:{},
    createGain() { const gain={value:0,setValueAtTime(){},linearRampToValueAtTime(){},exponentialRampToValueAtTime(){}};
      volumes.push(gain); return {gain,connect(){},disconnect(){}}; },
    createOscillator() {return {frequency:{value:0},connect(){},disconnect(){},start(at){played.push([this.frequency.value,at]);},stop(){}};},
    resume(){this.state="running";return Promise.resolve();},close(){this.closed=true;return Promise.resolve();}};
}
const job = (id,status,label="Generando imágenes") => ({id,status,label});
const frequencies = c => c.played.map(([frequency])=>frequency);
(async () => {
  const c=context(), audio=new GenerationSounds(()=>c);
  audio.unlock();
  audio.observe(job("one","queued"),true);
  audio.observe(job("one","running"));audio.observe(job("one","running"));
  assert.deepEqual(frequencies(c),[440,660],"queued/running polling emits one start");
  audio.observe(job("one","completed"));audio.observe(job("one","completed"));
  audio.observe(job("one","failed"));audio.observe(job("one","queued"));
  assert.deepEqual(frequencies(c),[440,660,660,880,1046],"terminal jobs never announce twice");
  assert.ok(c.played.every(([,at],i)=>!i || at>c.played[i-1][1]),"immediate completion follows the start sound");
  audio.observe(job("old","failed"));audio.observe(job("analysis","running","Analizando producto"));
  audio.observe(job("save","completed","Guardando producto"));
  assert.equal(c.played.length,5,"history and unrelated jobs are silent");
  audio.observe(job("correction","completed","Corrigiendo imagen"),true);
  assert.deepEqual(frequencies(c).slice(5),[440,660,660,880,1046],"fast correction announces both transitions");
  audio.observe(job("failure","queued"),true);
  // A network error leaves the job unchanged; the next running result is quiet.
  audio.observe(job("failure","running"));assert.equal(c.played.length,12);
  audio.observe(job("failure","failed"));
  assert.deepEqual(frequencies(c).slice(10),[440,660,330,220,165]);
  audio.setEnabled(false);assert.equal(c.volumes[0].value,0,"mute silences scheduled tones");
  audio.observe(job("muted","queued"),true);audio.observe(job("muted","completed"));
  audio.setEnabled(true);audio.observe(job("muted","completed"));
  assert.equal(c.played.length,15,"muting does not queue old notices");
  audio.dispose();assert.equal(c.closed,true);
  const blocked=context();blocked.state="suspended";blocked.resume=()=>Promise.reject(new Error("Audio blocked"));
  const optional=new GenerationSounds(()=>blocked);optional.unlock();optional.observe(job("blocked","failed"),true);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(blocked.played.length,0,"audio rejection cannot interrupt generation");
  const unavailable=new GenerationSounds(()=>null);unavailable.unlock();unavailable.observe(job("no-audio","completed"),true);
  console.log("Generation sounds: start/success/failure, deduplication, fast replies, history, mute and browser restrictions passed.");
})().catch(error=>{console.error(error);process.exitCode=1;});

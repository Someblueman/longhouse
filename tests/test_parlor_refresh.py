"""Run the real async refresh and Parlor renderer with a small DOM boundary."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("node"), "Node executes the actual renderer")
class ParlorRefreshTests(unittest.TestCase):
    def test_refresh_keeps_drafts_and_focus_without_changing_navigation(self):
        source = Path(__file__).parents[1] / "site/house.js"
        script = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.listeners={};this.dataset={};this.style={};this.classList={toggle(){}};}
  appendChild(node){this.children.push(node);return node;}
  replaceChildren(){if(all(this).includes(document.activeElement))document.activeElement=document.body;this.children=[];}
  querySelectorAll(selector){
    assert(['details','details[open]'].includes(selector));
    return this.children.flatMap(all).filter(n=>n.tag==='details'&&(selector==='details'||n.open));
  }
  setAttribute(k,v){this[k]=v;}
  addEventListener(k,fn){this.listeners[k]=fn;}
  focus(options){document.activeElement=this;this.focusOptions=options;}
}
const all=n=>[n,...n.children.flatMap(all)], nodes={};
const document={body:new Element('body'),activeElement:null,createElement:tag=>new Element(tag),
  getElementById(id){
    const found=Object.values(nodes).flatMap(all).find(n=>n.id===id);
    if(found)return found;
    if(id.startsWith('catchup-'))return null;
    return nodes[id]||(nodes[id]=Object.assign(new Element('div'),{id}));
  }};
document.activeElement=document.body;
let respond;
const fetch=()=>new Promise(resolve=>{respond=resolve;});
const ctx=vm.createContext({assert,document,fetch,AbortSignal,structuredClone,console});
const source=fs.readFileSync(process.argv[1],'utf8'),tail='refresh();\nsetInterval(refresh,60000);\n';
assert(source.endsWith(tail));vm.runInContext(source.slice(0,-tail.length),ctx);
vm.runInContext(`
// Unrelated drawing is outside this regression; real render, roomPanel and refresh run.
drawHouse=()=>{};floorControls=()=>{};dormControls=()=>{};accounts=()=>{};shelf=()=>{};lighting=()=>{};
const moment=(seq,op,title)=>({seq,at:100+seq,event:{op,title,actor:'a'},
 rooms:[{id:'parlor',name:'Parlor',status:'open'}],residents:[],tasks:[],scars:[],ambitions:[]});
const first=moment(1,'task','build');first.tasks=[{id:'build',title:'Build Parlor'}];
const second=moment(2,'finish','build');
data={version:1,journal_head:'a',source_head:'source',timezone:'Europe/London',observed_at:110,
 frames:[first,second],scars:{},commits:[]};index=1;selected='parlor';controlsReady=true;render();
`,ctx);
const get=id=>document.getElementById(id), run=s=>vm.runInContext(s,ctx);
const snapshot=()=>run('structuredClone(data)');
const complete=async(next,ok=true)=>{const pending=ctx.refresh();respond({ok,status:503,json:async()=>next});await pending;};
(async()=>{
  get('catchup-seq').value='2';get('catchup-apply').focus();
  await complete(snapshot()); // same-head minute refresh
  assert.equal(get('catchup-seq').value,'2');
  assert.equal(document.activeElement,get('catchup-apply'));
  assert.equal(document.activeElement.focusOptions.preventScroll,true);
  // Refresh does not apply an unsubmitted draft.
  assert.equal(run('catchupStartSeq'),null);
  get('catchup-seq').value='';get('catchup-seq').focus();
  await complete(null,false); // failed fetch still redraws clock-sensitive contents
  assert.equal(get('catchup-seq').value,'');assert.equal(document.activeElement,get('catchup-seq'));
  const next=snapshot();next.journal_head='b';next.frames.push({...next.frames[1],seq:3,event:{op:'say',actor:'a'}});
  const pending=ctx.refresh(); // a late edit/focus change must win over fetch-start state
  get('catchup-seq').value='3';get('catchup-reset').focus();
  respond({ok:true,json:async()=>next});await pending;
  assert.equal(get('catchup-seq').value,'3');assert.equal(document.activeElement,get('catchup-reset'));
  assert.equal(run('frame.seq'),3);
  // Manual Update and Latest 50 retain their original semantics.
  get('catchup-apply').listeners.click();assert.equal(run('catchupStartSeq'),3);
  get('catchup-reset').listeners.click();assert.equal(run('catchupStartSeq'),null);
  assert.equal(get('catchup-seq').value,'1');
  const jump=get('catchup-jump-0-2');assert(jump);jump.focus();
  await complete(snapshot());assert.equal(document.activeElement,get(jump.id));
  get(jump.id).listeners.click();assert.equal(run('frame.seq'),2);assert.equal(run('current'),false);
  // A newer publication must not move someone who scrubbed while fetch was pending.
  const newer=snapshot();newer.journal_head='c';newer.frames.push({...newer.frames[2],seq:4});
  run('index=2;current=true;render()');
  const inflight=ctx.refresh();ctx.jumpToSequence(2);get('catchup-seq').value='2';get('catchup-seq').focus();
  respond({ok:true,json:async()=>newer});await inflight;
  assert.equal(run('frame.seq'),2);assert.equal(run('current'),false);
  assert.equal(get('catchup-seq').value,'2');assert.equal(document.activeElement,get('catchup-seq'));
  // Focus outside the Parlor is not stolen.
  const outside=get('overview');outside.focus();await complete(snapshot());
  assert.equal(document.activeElement,outside);
  // An untouched default advances; a Jump aging out of the window is not resurrected.
  run('current=true;index=data.frames.length-1;render()');get('catchup-jump-0-2').focus();
  const long=snapshot();long.journal_head='d';
  for(let seq=5;seq<=60;seq++)long.frames.push({...long.frames[3],seq});
  await complete(long);
  assert.equal(get('catchup-seq').value,'11');assert.equal(get('catchup-jump-0-2'),null);
  assert.equal(document.activeElement,document.body);
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
        result = subprocess.run([shutil.which("node"), "-e", script, str(source)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

"""Run room scar memory navigation with the real renderer and a small DOM boundary."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("node"), "Node executes the actual renderer")
class RoomMemoryNavigationTests(unittest.TestCase):
    def test_scar_memory_navigation_and_inferred_bounds(self):
        source = Path(__file__).parents[1] / "site/house.js"
        script = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.listeners={};this.dataset={};this.style={};this.classList={toggle(){}};}
  appendChild(node){this.children.push(node);return node;}
  replaceChildren(){this.children=[];}
  querySelectorAll(selector){
    assert(['details','details[open]'].includes(selector));
    return this.children.flatMap(all).filter(n=>n.tag==='details'&&(selector==='details'||n.open));
  }
  setAttribute(k,v){this[k]=v;}
  addEventListener(k,fn){this.listeners[k]=fn;}
}
const all=n=>[n,...n.children.flatMap(all)], nodes={};
const document={body:new Element('body'),activeElement:null,createElement:tag=>new Element(tag),
  getElementById(id){
    const found=Object.values(nodes).flatMap(all).find(n=>n.id===id);
    if(found)return found;
    return nodes[id]||(nodes[id]=Object.assign(new Element('div'),{id}));
  }};
const ctx=vm.createContext({assert,document,fetch:()=>new Promise(()=>{}),AbortSignal,structuredClone,console});
const source=fs.readFileSync(process.argv[1],'utf8'),tail='refresh();\nsetInterval(refresh,60000);\n';
assert(source.endsWith(tail));vm.runInContext(source.slice(0,-tail.length),ctx);
vm.runInContext(`
drawHouse=()=>{};floorControls=()=>{};dormControls=()=>{};accounts=()=>{};shelf=()=>{};lighting=()=>{};
const moment=(seq,scars)=>({seq,at:1000+seq,event:{op:'say',actor:'a'},
  rooms:[{id:'workshop',name:'Workshop',status:'open'}],residents:[],tasks:[],scars,ambitions:[]});
const scarList=[
  {id:'s-valid',room:'workshop',title:'Recorded receipt',detail:'d1',sequence:20,basis:'Supervisor receipt',mended:false},
  {id:'s-inferred',room:'workshop',title:'Inferred lease',detail:'d2',sequence:20,basis:'Inferred from lease time; process fate unconfirmed',mended:false},
  {id:'s-future',room:'workshop',title:'Future seq',detail:'d3',sequence:999,basis:'Supervisor receipt',mended:false},
  {id:'s-bad',room:'workshop',title:'Malformed seq',detail:'d4',sequence:'20',basis:'Supervisor receipt',mended:false},
  {id:'s-missing',room:'workshop',title:'Missing seq',detail:'d5',sequence:15,basis:'Supervisor receipt',mended:false}
];
const laterScar=[
  {id:'s-later',room:'workshop',title:'Later than displayed frame',detail:'d6',sequence:50,basis:'Supervisor receipt',mended:false}
];
data={version:1,journal_head:'a',source_head:'source',timezone:'Europe/London',observed_at:1060,
  frames:[moment(10,[]),moment(20,laterScar),moment(50,scarList)],scars:{},commits:[]};
bindControls();index=2;current=true;selected='workshop';render();
`,ctx);
const get=id=>document.getElementById(id), run=s=>vm.runInContext(s,ctx);
const buttons=all(get('room-content')).filter(n=>n.tag==='button');
assert.equal(buttons.length,1);
assert.equal(buttons[0].type,'button');
assert.equal(buttons[0].textContent,'View event 20');
buttons[0].listeners.click();
assert.equal(run('frame.seq'),20);
assert.equal(run('current'),false);
assert.equal(run('selected'),'workshop');
// At historical frame seq 20, a scar pointing to later frame seq 50 must not offer a jump.
const historicalButtons=all(get('room-content')).filter(n=>n.tag==='button');
assert.equal(historicalButtons.length,0);
// Return to Latest via the actual bound Latest ("present") handler.
get('present').listeners.click();
assert.equal(run('frame.seq'),50);
assert.equal(run('current'),true);
assert.equal(run('selected'),'workshop');
'''
        proc = subprocess.run(
            ["node", "-e", script, str(source)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

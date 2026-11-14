"""Workshop task rows name declared readiness and recorded projects in the actual renderer."""
from pathlib import Path
import shutil
import subprocess
import unittest


SOURCE = Path(__file__).parents[1] / "site/house.js"
HARNESS = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.textContent='';this.className='';}
  appendChild(node){this.children.push(node);}
  replaceChildren(){this.children=[];}
  set innerHTML(value){throw new Error('Render text safely');}
  setAttribute(){}
  addEventListener(){}
}
const nodes={},get=id=>(nodes[id]||(nodes[id]=new Element('div')));
const document={getElementById:get,createElement:tag=>new Element(tag),createElementNS:(ns,tag)=>new Element(tag),querySelectorAll:()=>[]};
const text=node=>[node.textContent,...node.children.map(text)].join(' ');
const all=node=>[node,...node.children.flatMap(all)];
class FixedDate extends Date {static now(){return 2000000;}}
const context=vm.createContext({assert,document,nodes,text,all,Date:FixedDate});
const source=fs.readFileSync(process.argv[1],'utf8'),tail='refresh();\nsetInterval(refresh,60000);\n';
assert(source.endsWith(tail));vm.runInContext(source.slice(0,-tail.length),context);
vm.runInContext(`
data={timezone:'Europe/London'};current=true;selected='workshop';
const panel=()=>nodes['room-content'];
const rows=()=>all(panel()).filter(n=>n.className==='task'||n.className==='task expired');
`,context);
'''


@unittest.skipUnless(shutil.which("node"), "Node executes the actual house renderer")
class WorkshopUITests(unittest.TestCase):
    def run_renderer(self, setup, assertions):
        script = HARNESS + "\nvm.runInContext(" + repr(setup + assertions) + ",context);"
        result = subprocess.run(
            [shutil.which("node"), "-e", script, str(SOURCE)],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ready_blocked_unknown_and_project_titles(self):
        self.run_renderer(r'''
frame={seq:10,at:1000,rooms:[{id:'workshop',name:'Workshop'}],
 residents:[{id:'mallow',name:'Mallow',room:'hearth',pose:'standing'}],runs:[],scars:[],
 shelf:{projects:[{id:'night-ferry',title:'Night Ferry'}]},
 tasks:[
  {id:'routed-ready',title:'Build ferry',owner:null,status:'open',until:0,generation:0,ready:true,project:'night-ferry'},
  {id:'blocked',title:'Repair',owner:null,status:'open',until:0,generation:1,ready:false,project_id:'signal-garden-title-missing'},
  {id:'unknown',title:'Ordinary',owner:null,status:'open',until:0,generation:0},
  {id:'claimed-ready',title:'Claimed work',owner:'mallow',status:'claimed',until:3000,generation:2,ready:true}
 ]};
''', r'''
roomPanel();
assert.match(text(panel()),/4 unfinished · 3 unassigned · 1 recorded claims · 0 expired leases/);
const r=rows();assert.equal(r.length,4);
assert.equal(r[0].children[1].textContent,'Unassigned');
assert.equal(r[0].children[2].textContent,'Declared ready');
assert.equal(r[0].children[3].textContent,'Project: Night Ferry');
assert.equal(r[1].children[2].textContent,'Blocked (declared not ready)');
assert.equal(r[1].children[3].textContent,'Project: signal-garden-title-missing');
assert.equal(r[2].children[2].textContent,'Readiness unknown (unrecorded)');
assert.equal(r[2].children[3].textContent,'Ordinary house work — no project recorded');
assert.equal(r[3].children[1].textContent,'Recorded claim · Mallow');
assert.equal(r[3].children[2].textContent,'Declared ready');
''')

    def test_old_snapshots_without_fields_stay_unknown_and_ordinary(self):
        self.run_renderer(r'''
frame={seq:5,at:1000,rooms:[{id:'workshop',name:'Workshop'}],
 residents:[],runs:[],scars:[],
 tasks:[
  {id:'old',title:'<img src=x onerror=alert(1)>',owner:null,status:'open',until:0,generation:0},
  {id:'old-claimed',title:'Old claim',owner:'mallow',status:'claimed',until:3000,generation:1}
 ]};
''', r'''
roomPanel();
assert.match(text(panel()),/2 unfinished · 1 unassigned · 1 recorded claims · 0 expired leases/);
const r=rows();assert.equal(r.length,2);
assert.equal(r[0].children[2].textContent,'Readiness unknown (unrecorded)');
assert.equal(r[0].children[3].textContent,'Ordinary house work — no project recorded');
assert.equal(r[1].children[2].textContent,'Readiness unknown (unrecorded)');
assert.doesNotMatch(text(panel()),/Declared ready|Blocked \(declared not ready\)/);
assert.equal(all(panel()).filter(n=>n.tag==='img').length,0);
''')

    def test_null_readiness_and_missing_shelf_fall_back_to_id(self):
        self.run_renderer(r'''
frame={seq:5,at:1000,rooms:[{id:'workshop',name:'Workshop'}],
 residents:[],runs:[],scars:[],
 tasks:[
  {id:'nul',title:'Null readiness',owner:null,status:'open',until:0,generation:0,ready:null,project:'missing-shelf-project'}
 ]};
delete frame.shelf;
''', r'''
roomPanel();
const r=rows();assert.equal(r.length,1);
assert.equal(r[0].children[2].textContent,'Readiness unknown (unrecorded)');
assert.equal(r[0].children[3].textContent,'Project: missing-shelf-project');
''')


if __name__ == "__main__":
    unittest.main()

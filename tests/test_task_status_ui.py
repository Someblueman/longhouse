"""Exercise Workshop task labels and counts in the actual renderer; no visual claim."""
from pathlib import Path
import shutil
import subprocess
import unittest


SOURCE = Path(__file__).parents[1] / "site/house.js"
HARNESS = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.textContent='';}
  appendChild(node){this.children.push(node);}
  replaceChildren(){this.children=[];}
  set innerHTML(value){throw new Error('Render text safely');}
}
const nodes={},get=id=>(nodes[id]||(nodes[id]=new Element('div')));
const document={getElementById:get,createElement:tag=>new Element(tag)};
const text=node=>[node.textContent,...node.children.map(text)].join(' ');
const all=node=>[node,...node.children.flatMap(all)];
class FixedDate extends Date {static now(){return 2000000;}}
const context=vm.createContext({assert,document,nodes,text,all,Date:FixedDate});
const source=fs.readFileSync(process.argv[1],'utf8'),tail='refresh();\nsetInterval(refresh,60000);\n';
assert(source.endsWith(tail));vm.runInContext(source.slice(0,-tail.length),context);
vm.runInContext(`
data={timezone:'Europe/London'};current=true;selected='workshop';
frame={seq:10,at:1000,rooms:[{id:'workshop',name:'Workshop'},{id:'door',name:'Door'}],
 residents:[{id:'mallow',name:'Mallow',room:'hearth',pose:'standing'}],runs:[],scars:[],tasks:[
  {id:'open',title:'<img src=x onerror=alert(1)>',owner:null,status:'open',until:0,generation:0},
  {id:'claimed',title:'Build',owner:'mallow',status:'claimed',until:3000,generation:1},
  {id:'expired',title:'Repair',owner:'mallow',status:'claimed',until:1500,generation:1}
 ]};
const panel=()=>nodes['room-content'];
const rows=()=>all(panel()).filter(n=>n.className==='task'||n.className==='task expired');
`,context);
'''


@unittest.skipUnless(shutil.which("node"), "Node executes the actual house renderer")
class TaskStatusUITests(unittest.TestCase):
    def run_renderer(self, assertions):
        script = HARNESS + "\nvm.runInContext(" + repr(assertions) + ",context);"
        result = subprocess.run(
            [shutil.which("node"), "-e", script, str(SOURCE)],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unfinished_counts_claims_and_safe_unassigned_label(self):
        self.run_renderer(r'''
const before=JSON.stringify(frame);
roomPanel();
assert.match(text(panel()),/3 unfinished · 1 unassigned · 1 recorded claims · 1 expired leases/);
assert.match(text(panel()),/Unassigned does not mean ready to start/);
assert.match(text(panel()),/Recorded claims exclude expired leases and are not live process status/);
assert.equal(rows().length,3);
assert.equal(rows()[0].children[1].textContent,'Unassigned');
assert.equal(rows()[1].children[1].textContent,'Recorded claim · Mallow');
assert.equal(rows()[2].children[1].textContent,'Lease expired · fate unconfirmed · Mallow');
assert.equal(rows()[2].className,'task expired');
assert.doesNotMatch(text(panel()),/available|blocked|completed/);
assert.equal(rows()[0].children[0].textContent,'<img src=x onerror=alert(1)>');
assert.equal(all(panel()).filter(n=>n.tag==='img').length,0);
assert.equal(JSON.stringify(frame),before);
// The whole-floor view uses the same summary and task rows.
selected=null;roomPanel();
assert.match(text(panel()),/3 unfinished · 1 unassigned · 1 recorded claims · 1 expired leases/);
assert.equal(rows().length,3);
selected='door';roomPanel();
assert.equal(rows().length,0);
assert.doesNotMatch(text(panel()),/unfinished|readiness/);
''')

    def test_history_and_current_clock_expiry_boundary(self):
        self.run_renderer(r'''
current=false;roomPanel();
assert.match(text(panel()),/3 unfinished · 1 unassigned · 2 recorded claims · 0 expired leases/);
assert.equal(rows()[2].children[1].textContent,'Recorded claim · Mallow');
frame.at=1500;roomPanel();
assert.equal(rows()[2].children[1].textContent,'Lease expired · fate unconfirmed · Mallow');
frame.at=1499;roomPanel();
assert.equal(rows()[2].children[1].textContent,'Recorded claim · Mallow');
current=true;roomPanel();
assert.equal(rows()[2].children[1].textContent,'Lease expired · fate unconfirmed · Mallow');
assert.match(text(panel()),/3 unfinished · 1 unassigned · 1 recorded claims · 1 expired leases/);
''')

    def test_missing_resident_and_empty_snapshot_do_not_advertise_work(self):
        self.run_renderer(r'''
frame.residents=[];roomPanel();
assert.equal(rows()[1].children[1].textContent,'Recorded claim · mallow');
assert.doesNotMatch(text(panel()),/available/);
frame.tasks=[];roomPanel();
assert.match(text(panel()),/0 unfinished · 0 unassigned · 0 recorded claims · 0 expired leases/);
assert.equal(rows().length,0);
assert.doesNotMatch(text(panel()),/Build|Repair|<img/);
''')


if __name__ == "__main__":
    unittest.main()

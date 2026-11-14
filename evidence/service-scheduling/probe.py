import json, subprocess, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from house.record import Record
phase=sys.argv[2]
with tempfile.TemporaryDirectory(prefix='emberhall-qos-probe-') as temporary:
 root=Path(temporary)
 subprocess.run(['git','init','-q',str(root)],check=True)
 record=Record(root); record.found('Inert scheduling probe','Fixture rules')
 record.append('arrive','probe',{'name':'Probe'})
 start=time.perf_counter()
 for index in range(25):
  record.append('say','probe',{'text':'fixed local probe payload ' * 40},request=f'probe-{index}')
 wall=time.perf_counter()-start
 state,events,head=record.read()
 assert len(events)==27
 print(json.dumps({'phase':phase,'appends':25,'events':len(events),'wall_seconds':wall,'process_priority':subprocess.check_output(['ps','-p',str(__import__('os').getpid()),'-o','ni=,pri='],text=True).strip()}))

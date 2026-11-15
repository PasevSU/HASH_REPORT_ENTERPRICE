import argparse,json,sys
from hash_report_generator.process_runtime import execute,verify
def main():
 p=argparse.ArgumentParser();p.add_argument('--profile',required=True);p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--allow-unsealed-diagnostics',action='store_true');a=p.parse_args()
 try:
  run=execute(a.profile,a.source,a.output,allow_unsealed=a.allow_unsealed_diagnostics);print(json.dumps({'run_dir':str(run),**verify(run)},ensure_ascii=False));return 0
 except Exception as e:print(f'BLOCKED/FAILED: {type(e).__name__}: {e}',file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())

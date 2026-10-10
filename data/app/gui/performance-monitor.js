'use strict';
const os=require('node:os');
const {performance,monitorEventLoopDelay}=require('node:perf_hooks');
class PerformanceMonitor {
 constructor({clock=()=>performance.now(),cpu=()=>process.cpuUsage(),io=()=>process.resourceUsage(),lagMonitor=monitorEventLoopDelay({resolution:20})}={}){this.clock=clock;this.cpu=cpu;this.io=io;this.lag=lagMonitor;this.prev=null;this.started=false;}
 start(){if(!this.started){this.lag.enable();this.started=true;}return this;}
 sample(){const time=this.clock(),cpu=this.cpu(),io=this.io();const free=os.freemem()/os.totalmem();const elapsed=this.prev?Math.max(1,time-this.prev.time):0;const cores=Math.max(1,os.availableParallelism?.()||os.cpus().length);const processCpu=this.prev?Math.min(1,Math.max(0,((cpu.user-this.prev.cpu.user)+(cpu.system-this.prev.cpu.system))/(elapsed*1000*cores))):0;const ioOps=this.prev?Math.max(0,(io.fsRead+io.fsWrite-this.prev.io.fsRead-this.prev.io.fsWrite)*1000/elapsed):0;const lagMs=this.started&&Number.isFinite(this.lag.mean)?this.lag.mean/1e6:0;this.lag.reset();this.prev={time,cpu,io};return {free,cpu:processCpu,eventLoopLagMs:lagMs,processCpu,ioOpsPerSecond:ioOps,ioUnit:'operations/s',cpuScope:'process / available cores',networkBytesPerSecond:null,networkStatus:'not measured'};}
 close(){if(this.started)this.lag.disable();this.started=false;}
}
module.exports={PerformanceMonitor};

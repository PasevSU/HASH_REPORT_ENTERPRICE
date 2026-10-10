'use strict';
const os=require('node:os');
class SystemMonitor {
 constructor({readCpus=()=>os.cpus(),readMemory=()=>({free:os.freemem(),total:os.totalmem()}),clock=()=>Date.now()}={}) {this.readCpus=readCpus;this.readMemory=readMemory;this.clock=clock;this.previous=null;}
 sample(){const cpus=this.readCpus();let idle=0,total=0;for(const core of cpus){for(const [k,v] of Object.entries(core.times)){total+=v;if(k==='idle')idle+=v;}}const memory=this.readMemory();const valid=Number.isFinite(memory.free)&&Number.isFinite(memory.total)&&memory.total>0&&memory.free>=0&&memory.free<=memory.total;if(!valid)throw Error('Invalid memory sample');let cpu=null;if(this.previous){const dt=total-this.previous.total,di=idle-this.previous.idle;if(dt>0&&di>=0&&di<=dt)cpu=Math.max(0,Math.min(1,1-di/dt));}this.previous={idle,total};return {cpu,free:memory.free/memory.total,scope:'system',sampledAt:this.clock()};}
}
module.exports={SystemMonitor};

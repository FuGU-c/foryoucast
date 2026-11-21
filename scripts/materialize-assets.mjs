import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {dirname,resolve,sep} from 'node:path';
import {fileURLToPath} from 'node:url';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const bundle=JSON.parse(await readFile(resolve(root,'assets/embedded-images.json'),'utf8'));
if(bundle.format!==1||!Array.isArray(bundle.files))throw new Error('Unsupported image bundle');
let restored=0;
for(const file of bundle.files){
 const target=resolve(root,file.path);
 if(!target.startsWith(root+sep)||!(/^(public\/|docs\/color-proposals(?:-v2)?\/)/.test(file.path)))throw new Error('Invalid image path');
 const data=Buffer.from(file.content,'base64');
 const hash=value=>createHash('sha256').update(value).digest('hex');
 if(hash(data)!==file.sha256)throw new Error('Image integrity check failed: '+file.path);
 try{if(hash(await readFile(target))===file.sha256)continue;}catch(error){if(error.code!=='ENOENT')throw error;}
 await mkdir(dirname(target),{recursive:true});
 await writeFile(target,data);restored++;
}
console.log(`Image assets verified: ${bundle.files.length}; restored: ${restored}.`);

#!/usr/bin/env node
/**
 * Upload Spooky2 preset category files to file.kiwi
 *
 * Usage:
 *   node scripts/upload_to_filekiwi.js
 *
 * Requires:
 *   npm install @file-kiwi/node
 *
 * Outputs:
 *   - Download URLs for each category file
 *   - Updates notebooklm-manifest.json with download URLs
 */

import { createWebFolder, startUpload } from '@file-kiwi/node';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BASE_DIR = path.resolve(__dirname, '..');
const DOWNLOADS_DIR = path.join(BASE_DIR, 'downloads', 'notebooklm');
const MANIFEST_PATH = path.join(BASE_DIR, 'spooky2-search', 'public', 'data', 'notebooklm-manifest.json');

const MAX_FILES_PER_BATCH = 10;

async function uploadBatch(batchFiles, batchIndex, totalBatches) {
  console.log(`\n--- Batch ${batchIndex + 1}/${totalBatches} (${batchFiles.length} files) ---`);
  
  const webfolder = await createWebFolder({
    title: `Spooky2 Presets Batch ${batchIndex + 1}`,
    files: batchFiles.map(f => ({ filepath: f.filepath }))
  });

  console.log(`WebFolder created: ${webfolder.webfolderUrl}`);
  
  await startUpload(webfolder, {
    onProgress: (file, uploaded, total) => {
      const pct = Math.round((uploaded / total) * 100);
      process.stdout.write(`\r  ${path.basename(file.filepath)}: ${pct}%`);
    },
    onFileComplete: (file) => {
      console.log(`\n  ✓ ${path.basename(file.filepath)} complete`);
    },
    onError: (file, error) => {
      console.error(`\n  ✗ ${path.basename(file.filepath)} failed: ${error.message}`);
    }
  });

  return webfolder;
}

async function main() {
  // Check if downloads directory exists
  if (!fs.existsSync(DOWNLOADS_DIR)) {
    console.error(`Downloads directory not found: ${DOWNLOADS_DIR}`);
    console.error('Run: python3 scripts/prepare_notebooklm_uploads.py');
    process.exit(1);
  }

  // Get all JSON files from downloads directory
  const files = fs.readdirSync(DOWNLOADS_DIR)
    .filter(f => f.endsWith('.json'))
    .map(f => ({
      filepath: path.join(DOWNLOADS_DIR, f),
      name: f,
      size: fs.statSync(path.join(DOWNLOADS_DIR, f)).size
    }));

  if (files.length === 0) {
    console.error('No JSON files found in downloads directory.');
    console.error('Run: python3 scripts/prepare_notebooklm_uploads.py');
    process.exit(1);
  }

  console.log(`Found ${files.length} files to upload:`);
  files.forEach(f => {
    const sizeMB = (f.size / 1024 / 1024).toFixed(1);
    console.log(`  - ${f.name} (${sizeMB} MB)`);
  });

  // Split into batches
  const batches = [];
  for (let i = 0; i < files.length; i += MAX_FILES_PER_BATCH) {
    batches.push(files.slice(i, i + MAX_FILES_PER_BATCH));
  }

  console.log(`\nWill create ${batches.length} WebFolder(s) due to 10-file limit per batch`);

  // Load existing manifest
  let manifest = { categories: [] };
  if (fs.existsSync(MANIFEST_PATH)) {
    manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf-8'));
  }

  // Upload each batch
  const results = [];
  for (let i = 0; i < batches.length; i++) {
    const webfolder = await uploadBatch(batches[i], i, batches.length);
    results.push(webfolder);
  }

  console.log('\n=== All batches uploaded successfully! ===\n');

  // Update manifest with download URLs
  // Each batch has its own WebFolder URL
  for (const webfolder of results) {
    for (const uploadedFile of webfolder.files) {
      const fileName = path.basename(uploadedFile.filepath);
      const cat = manifest.categories.find(c => c.file === fileName);
      if (cat) {
        cat.download_url = webfolder.webfolderUrl;
      }
    }
  }

  // Write updated manifest
  fs.writeFileSync(MANIFEST_PATH, JSON.stringify(manifest, null, 2));
  console.log(`Manifest updated: ${MANIFEST_PATH}`);

  // Output summary
  console.log('\n=== Upload Summary ===');
  for (const webfolder of results) {
    console.log(`Batch: ${webfolder.webfolderUrl}`);
  }
  console.log(`\nTotal files uploaded: ${files.length}`);
  console.log('Download URLs have been added to the manifest.');
  console.log('Redeploy the website to make links available.');
}

main().catch(err => {
  console.error('Upload failed:', err.message);
  process.exit(1);
});

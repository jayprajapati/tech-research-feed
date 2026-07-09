export async function getContainer() {
  const { BlobServiceClient } = await import('@azure/storage-blob');
  const conn = process.env.AZURE_STORAGE_CONNECTION_STRING;
  if (!conn) return null;
  return BlobServiceClient.fromConnectionString(conn).getContainerClient(process.env.AZURE_STORAGE_CONTAINER || 'reports');
}

export async function getReportManifest() {
  const c = await getContainer();
  if (!c) return [];
  const r = await c.getBlockBlobClient('index.json').downloadToBuffer();
  return JSON.parse(r.toString());
}

export async function getReport(date, slug) {
  const c = await getContainer();
  if (!c) return null;
  const r = await c.getBlockBlobClient(`${date}/${slug}.json`).downloadToBuffer();
  return JSON.parse(r.toString());
}

import { BlobServiceClient, ContainerClient } from '@azure/storage-blob';

interface ReportManifest {
  date: string;
  type: 'daily-pulse' | 'weekly-review' | 'swing-analysis' | 'portfolio-audit';
  title: string;
  tags: string[];
  summary: string;
  slug: string;
}

interface Report extends ReportManifest {
  sections: Section[];
  generatedAt: string;
  model: string;
}

interface Section {
  heading: string;
  content: string | Table | Card[];
  type: 'text' | 'table' | 'cards' | 'ranking';
}

interface Table {
  headers: string[];
  rows: string[][];
  caption?: string;
}

interface Card {
  name: string;
  tier?: string;
  reasoning: string;
  metrics: Record<string, string>;
}

let _container: ContainerClient | null = null;

function getContainer(): ContainerClient | null {
  if (_container) return _container;
  const conn = process.env.AZURE_STORAGE_CONNECTION_STRING;
  if (!conn) return null;
  _container = BlobServiceClient
    .fromConnectionString(conn)
    .getContainerClient(process.env.AZURE_STORAGE_CONTAINER || 'reports');
  return _container;
}

async function downloadJson<T>(blobPath: string): Promise<T | null> {
  const container = getContainer();
  if (!container) return null;
  const client = container.getBlockBlobClient(blobPath);
  const response = await client.downloadToBuffer();
  return JSON.parse(response.toString());
}

export async function getReportManifest(): Promise<ReportManifest[]> {
  return (await downloadJson<ReportManifest[]>('index.json')) || [];
}

export async function getReport(date: string, slug: string): Promise<Report | null> {
  return downloadJson<Report>(`${date}/${slug}.json`);
}

export async function getAllTags(): Promise<string[]> {
  const reports = await getReportManifest();
  return [...new Set(reports.flatMap(r => r.tags))].sort();
}

import { BlobServiceClient } from '@azure/storage-blob';

const connectionString = process.env.AZURE_STORAGE_CONNECTION_STRING!;
const containerName = process.env.AZURE_STORAGE_CONTAINER || 'reports';

const containerClient = BlobServiceClient
  .fromConnectionString(connectionString)
  .getContainerClient(containerName);

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

async function downloadJson<T>(blobPath: string): Promise<T> {
  const client = containerClient.getBlockBlobClient(blobPath);
  const response = await client.downloadToBuffer();
  return JSON.parse(response.toString());
}

export async function getReportManifest(): Promise<ReportManifest[]> {
  return downloadJson<ReportManifest[]>('index.json');
}

export async function getReport(date: string, slug: string): Promise<Report> {
  return downloadJson<Report>(`${date}/${slug}.json`);
}

export async function getAllTags(): Promise<string[]> {
  const reports = await getReportManifest();
  return [...new Set(reports.flatMap(r => r.tags))].sort();
}

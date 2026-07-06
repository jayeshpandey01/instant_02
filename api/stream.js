export const config = {
  runtime: 'edge',
};

export default async function handler(req) {
  const url = new URL(req.url);
  const targetUrl = url.searchParams.get('url');
  const filename = url.searchParams.get('filename') || 'download.mp4';

  if (!targetUrl) {
    return new Response('Missing url', { status: 400 });
  }

  try {
    const response = await fetch(targetUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': '*/*'
      }
    });

    if (!response.ok) {
      return new Response('Failed to fetch from proxy', { status: response.status });
    }

    const headers = new Headers(response.headers);
    headers.set('Content-Disposition', `attachment; filename="${filename}"`);
    headers.delete('Content-Security-Policy');
    headers.delete('X-Frame-Options');

    return new Response(response.body, {
      status: response.status,
      headers: headers
    });
  } catch (e) {
    return new Response(e.message, { status: 500 });
  }
}

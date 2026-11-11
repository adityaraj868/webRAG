// WebRAG Content Script
// Extracts clean page content, title, headings, and readable body

export interface ExtractedPageContent {
  url: string;
  title: string;
  headings: string[];
  text: string;
  html: string;
}

function extractHeadings(): string[] {
  const headings: string[] = [];
  const headingElements = document.querySelectorAll('h1, h2, h3');
  headingElements.forEach((el) => {
    const text = (el.textContent || '').trim();
    if (text.length > 0 && text.length < 200) {
      headings.push(text);
    }
  });
  return headings.slice(0, 30);
}

function cleanAndExtractText(): string {
  // Clone body so we don't mutate active webpage DOM
  const clone = document.body.cloneNode(true) as HTMLElement;

  // Remove scripts, styles, iframes, nav, footer, headers, ads
  const selectorsToRemove = [
    'script',
    'style',
    'noscript',
    'iframe',
    'svg',
    'header',
    'footer',
    'nav',
    'aside',
    '.nav',
    '.navbar',
    '.footer',
    '.sidebar',
    '.ad',
    '.advertisement',
    '#comments',
  ];

  selectorsToRemove.forEach((selector) => {
    const elements = clone.querySelectorAll(selector);
    elements.forEach((el) => el.remove());
  });

  // Extract from main or article if available
  const mainElement = clone.querySelector('main, article, [role="main"]');
  const targetElement = (mainElement as HTMLElement) || clone;

  const rawText = targetElement.innerText || targetElement.textContent || '';

  // Normalize whitespace: collapse multiple empty lines into at most 2, strip excessive spacing
  return rawText
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .join('\n\n');
}

export function extractPage(): ExtractedPageContent {
  const url = window.location.href;
  const title = (document.title || '').trim() || document.querySelector('h1')?.textContent?.trim() || 'Untitled Page';
  const headings = extractHeadings();
  const text = cleanAndExtractText();
  const html = document.documentElement.outerHTML;

  return {
    url,
    title,
    headings,
    text,
    html,
  };
}

// Listen for requests from side panel or background
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === 'EXTRACT_PAGE_CONTENT') {
    try {
      const data = extractPage();
      sendResponse({ success: true, data });
    } catch (err) {
      console.error('[WebRAG] Error extracting page content:', err);
      sendResponse({ success: false, error: (err as Error).message });
    }
  }
  return true;
});

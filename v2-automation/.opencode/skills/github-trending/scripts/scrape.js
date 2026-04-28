const https = require('https');

const TOPICS_FILTER = ['ai', 'llm', 'agent', 'ml', 'machine-learning', 'deep-learning', 'nlp', 'large-language-model', 'generative-ai', 'gpt', 'llm-agent', 'ai-agent', 'rag', 'vector-database', 'langchain', 'autonomous', 'neural', 'transformer', 'chatbot'];

function fetch(url) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(data));
    }).on('error', reject);
  });
}

function isAIRelated(topics) {
  return topics.some(t => TOPICS_FILTER.some(f => t.includes(f)));
}

function parseRepoInfo(article) {
  const h2Match = /<h2[^>]*>[\s\S]*?<a[^>]*href="\/([^"]+\/[^"]+)"[^>]*>/.exec(article);
  if (!h2Match) return null;

  const name = h2Match[1];
  if (name.includes('/sponsors/')) return null;

  const url = `https://github.com/${name}`;

  const descMatch = /<p[^>]*class="[^"]*color-fg-muted[^"]*"[^>]*>([^<]+)<\/p>/.exec(article);
  const description = descMatch ? descMatch[1].trim() : '';

  const starsMatch = article.match(/(\d+[.,]?\d*[kKmM]?)/);
  const stars = starsMatch ? starsMatch[1] : '0';

  const topics = [];
  const topicRegex = /<a[^>]*topic[^>]*>([^<]+)<\/a>/g;
  let match;
  while ((match = topicRegex.exec(article)) !== null) {
    topics.push(match[1].toLowerCase().trim());
  }

  return { name, url, stars, topics, description };
}

function parseTrending(html) {
  const repos = [];
  const parts = html.split(/<article[^>]*class="Box-row"[^>]*>/);

  for (let i = 1; i < parts.length; i++) {
    const section = parts[i];
    const endIndex = section.indexOf('</article>');
    const article = endIndex > 0 ? section.substring(0, endIndex) : section;

    const repo = parseRepoInfo(article);
      if (repo && isAIRelated(repo.topics)) {
        repos.push(repo);
    }
  }

  return repos;
}

async function main() {
  try {
    const html = await fetch('https://github.com/trending');
    const repos = parseTrending(html);
    console.log(JSON.stringify(repos.slice(0, 50), null, 2));
  } catch (err) {
    console.error('Error:', err.message);
    console.log('[]');
    process.exit(0);
  }
}

main();
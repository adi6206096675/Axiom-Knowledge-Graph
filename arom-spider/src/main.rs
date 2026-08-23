use axum::{routing::post, Json, Router};
use redis::AsyncCommands;
use scraper::{Html, Selector};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::sync::Arc;
use tokio::sync::Mutex;
use tokio::time::{sleep, Duration};
use url::Url;

#[derive(Deserialize)]
struct CrawlRequest {
    target_urls: Vec<String>,
}

#[derive(Serialize)]
struct CrawlResponse {
    url: String,
    clean_paragraphs: Vec<String>,
}

// Added Serialize and Deserialize to allow saving to disk
#[derive(Serialize, Deserialize, Default)]
struct SpiderState {
    visited_urls: HashSet<String>,
    url_queue: Vec<String>,
}

// NEW: Structured payload to send text, url, and image to Redis
#[derive(Serialize)]
struct PipelinePayload {
    text: String,
    source_url: String,
    image_url: String,
}

// EXPANDED DOMAIN MATRIX: Trusted domains allowed into the Axiom Knowledge Graph
const ALLOWED_DOMAINS: &[&str] = &[
    "en.wikipedia.org",
    "wikihow.com",
    "www.wikihow.com",
    "britannica.com",
    "www.britannica.com",
    "reddit.com",
    "www.reddit.com",
    "quora.com",
    "www.quora.com",
    "stackoverflow.com",
    "www.stackoverflow.com",
    "youtube.com",
    "www.youtube.com",
    "vimeo.com",
    "www.vimeo.com",
    "tiktok.com",
    "www.tiktok.com",
    "nytimes.com",
    "www.nytimes.com",
    "theguardian.com",
    "www.theguardian.com",
    "bbc.com",
    "www.bbc.com",
    "reuters.com",
    "www.reuters.com",
    "forbes.com",
    "www.forbes.com",
    "businessinsider.com",
    "www.businessinsider.com",
    "medium.com",
    "www.medium.com",
    "pubmed.ncbi.nlm.nih.gov",
    "arxiv.org",
    "www.arxiv.org",
    "nature.com",
    "www.nature.com",
    "sciencedirect.com",
    "www.sciencedirect.com",
    "webmd.com",
    "www.webmd.com",
    "healthline.com",
    "www.healthline.com",
    "medicalnewstoday.com",
    "www.medicalnewstoday.com",
    "techradar.com",
    "www.techradar.com",
    "cnet.com",
    "www.cnet.com",
    "tomsguide.com",
    "www.tomsguide.com",
    "consumerreports.org",
    "www.consumerreports.org",
    "amazon.com",
    "www.amazon.com",
    "alibaba.com",
    "www.alibaba.com",
    "etsy.com",
    "www.etsy.com",
    "target.com",
    "www.target.com",
    "walmart.com",
    "www.walmart.com",
    "bestbuy.com",
    "www.bestbuy.com",
    "linkedin.com",
    "www.linkedin.com",
    "crunchbase.com",
    "www.crunchbase.com",
    "tripadvisor.com",
    "www.tripadvisor.com",
    "yelp.com",
    "www.yelp.com",
    "duckduckgo.com",
    "www.duckduckgo.com",
    "search.brave.com",
    "kagi.com",
    "www.kagi.com",
    "qwant.com",
    "www.qwant.com",
    "swisscows.com",
    "www.swisscows.com",
    "mojeek.com",
    "www.mojeek.com",
    "searx.org",
    "www.searx.org",
    "khanacademy.org",
    "coursera.org",
    "edx.org",
    "openstax.org",
    "ocw.mit.edu",
    "gutenberg.org",
    "usgs.gov",
    "noaa.gov",
    "census.gov",
    "europa.eu",
    "data.un.org",
    "worldbank.org",
    "who.int",
    "springer.com",
    "ieee.org",
    "acm.org",
    "cern.ch",
    "thehindu.com",
    "indianexpress.com",
    "hindustantimes.com",
    "timesofindia.com",
    "business-standard.com",
    "livemint.com",
    "ndtv.com",
    "india.gov.in",
    "data.gov.in",
    "meity.gov.in",
    "mohfw.gov.in",
    "rbi.org.in",
    "uidai.gov.in",
    "ugc.ac.in",
    "nptel.ac.in",
    "icmr.nic.in",
    "csir.res.in",
    "iitd.ac.in",
    "iitb.ac.in",
];

// List of MediaWiki namespaces that carry meta noise, not facts
const BLOCKED_NAMESPACES: &[&str] = &[
    // Wikipedia & Wikihow
    "Special:",
    "Wikipedia:",
    "Talk:",
    "Help:",
    "Portal:",
    "File:",
    "User:",
    "Category:",
    "Draft:",
    "MediaWiki:",
    "Template:",
    ".gz", ".zip", ".tar", ".bz2", ".xz", ".7z",
    ".seq", ".fasta", ".fa", ".fna", ".bam", ".sam",
    ".pdf", ".iso", ".bin", ".exe", ".dmg", ".mp4", ".mp3"

    // Reddit & Quora
    "/r/",
    "/user/",
    "/profile/",
    "/comments/",

    // StackOverflow
    "/users/",
    "/jobs/",
    "/help/",
    "/tags/",

    // YouTube, Vimeo, TikTok
    "/channel/",
    "/user/",
    "/playlist/",
    "/shorts/",
    "/watch?v=", // keep only if you want video metadata, otherwise block

    // News sites (NYT, Guardian, BBC, Reuters, etc.)
    "/comments/",
    "/live/",
    "/interactive/",
    "/video/",

    // Commerce (Amazon, Walmart, etc.)
    "/gp/help/",
    "/customer-reviews/",
    "/profile/",
    "/wishlist/",
    "/cart/",
    "/account/",

    // LinkedIn, Crunchbase
    "/company/",
    "/school/",
    "/groups/",
    "/jobs/",
    "/signup/",
    "/login/",

    // Travel & Local (TripAdvisor, Yelp)
    "/profile/",
    "/member/",
    "/forum/",
    "/help/",

    // Search engines (DuckDuckGo, Brave, Kagi, Qwant, Swisscows, Mojeek, Searx)
    "/settings/",
    "/about/",
    "/privacy/",
    "/help/",
    "/feedback/",

    // Indian News & Media
    "/epaper/",
    "/photos/",
    "/videos/",
    "/blogs/",
    "/opinion/",
    "/cartoons/",

    // Indian Government & Education
    "/contactus/",
    "/feedback/",
    "/tenders/",
    "/vacancy/",
    "/login/",
    "/downloads/",
    "/forms/",
];

fn is_valid_article_url(url_str: &str) -> bool {
    let Ok(mut parsed) = Url::parse(url_str) else {
        return false;
    };

    let Some(host) = parsed.host_str() else {
        return false;
    };

    // 1. Host check: Dynamic checks for .edu and .gov automatically cover other gov sites
    let is_trusted = ALLOWED_DOMAINS.contains(&host) || host.ends_with(".edu") || host.ends_with(".gov");
    if !is_trusted {
        return false;
    }

    // 2. Reject query params and anchor fragments (?action=edit, #section)
    if parsed.query().is_some() || parsed.fragment().is_some() {
        return false;
    }

    let path = parsed.path();

    // 3. MediaWiki Namespace Filter (applied to Wikipedia, OSDev, Grokipedia)
    if host.contains("wikipedia.org") || host.contains("osdev.org") || host.contains("grokipedia.org") {
        if !path.starts_with("/wiki/") {
            return false;
        }

        let article_part = &path["/wiki/".len()..];

        // Reject administrative namespaces and main page loop
        for ns in BLOCKED_NAMESPACES {
            if article_part.starts_with(ns) {
                return false;
            }
        }

        if article_part.is_empty() || article_part == "Main_Page" {
            return false;
        }
    }

    true
}

#[tokio::main]
async fn main() {
    println!("[AXIOM BOT] Initializing Multi-Domain Autonomous Engine...");

    let state_file = "axiom_crawler_state.json";
    
    // 1. BOOT SEQUENCE: Attempt to load previous state from disk
    let initial_state = if let Ok(data) = std::fs::read_to_string(state_file) {
        println!("[AXIOM BOT] Resuming from saved disk state...");
        serde_json::from_str(&data).unwrap_or_else(|_| SpiderState::default())
    } else {
        println!("[AXIOM BOT] No previous state found. Loading Expanded Scientific Seeds...");
        SpiderState {
            visited_urls: HashSet::new(),
            url_queue: vec![
                            // --- Existing Phase‑1 seeds ---
            "https://en.wikipedia.org/".to_string(),
            "https://wikihow.com/".to_string(),
            "https://britannica.com/".to_string(),
            "https://reddit.com/".to_string(),
            "https://quora.com/".to_string(),
            "https://stackoverflow.com/".to_string(),
            "https://youtube.com/".to_string(),
            "https://vimeo.com/".to_string(),
            "https://tiktok.com/".to_string(),
            "https://nytimes.com/".to_string(),
            "https://theguardian.com/".to_string(),
            "https://bbc.com/".to_string(),
            "https://reuters.com/".to_string(),
            "https://forbes.com/".to_string(),
            "https://businessinsider.com/".to_string(),
            "https://medium.com/".to_string(),
            "https://pubmed.ncbi.nlm.nih.gov/".to_string(),
            "https://arxiv.org/".to_string(),
            "https://nature.com/".to_string(),
            "https://sciencedirect.com/".to_string(),
            "https://webmd.com/".to_string(),
            "https://healthline.com/".to_string(),
            "https://medicalnewstoday.com/".to_string(),
            "https://techradar.com/".to_string(),
            "https://cnet.com/".to_string(),
            "https://tomsguide.com/".to_string(),
            "https://consumerreports.org/".to_string(),
            "https://amazon.com/".to_string(),
            "https://alibaba.com/".to_string(),
            "https://etsy.com/".to_string(),
            "https://target.com/".to_string(),
            "https://walmart.com/".to_string(),
            "https://bestbuy.com/".to_string(),
            "https://linkedin.com/".to_string(),
            "https://crunchbase.com/".to_string(),
            "https://tripadvisor.com/".to_string(),
            "https://yelp.com/".to_string(),
            "https://duckduckgo.com/".to_string(),
            "https://search.brave.com/".to_string(),
            "https://kagi.com/".to_string(),
            "https://qwant.com/".to_string(),
            "https://swisscows.com/".to_string(),
            "https://mojeek.com/".to_string(),
            "https://searx.org/".to_string(),

            // --- Phase‑2 Education ---
            "https://khanacademy.org/".to_string(),
            "https://coursera.org/".to_string(),
            "https://edx.org/".to_string(),
            "https://openstax.org/".to_string(),
            "https://ocw.mit.edu/".to_string(),
            "https://gutenberg.org/".to_string(),

            // --- Phase‑2 Government & Global Data ---
            "https://usgs.gov/".to_string(),
            "https://noaa.gov/".to_string(),
            "https://census.gov/".to_string(),
            "https://europa.eu/".to_string(),
            "https://data.un.org/".to_string(),
            "https://worldbank.org/".to_string(),
            "https://who.int/".to_string(),

            // --- Phase‑2 Research & Technical ---
            "https://springer.com/".to_string(),
            "https://ieee.org/".to_string(),
            "https://acm.org/".to_string(),
            "https://cern.ch/".to_string(),

            // --- Indian News & Media ---
            "https://thehindu.com/".to_string(),
            "https://indianexpress.com/".to_string(),
            "https://hindustantimes.com/".to_string(),
            "https://timesofindia.com/".to_string(),
            "https://business-standard.com/".to_string(),
            "https://livemint.com/".to_string(),
            "https://ndtv.com/".to_string(),

            // --- Indian Government & Official Data ---
            "https://india.gov.in/".to_string(),
            "https://data.gov.in/".to_string(),
            "https://meity.gov.in/".to_string(),
            "https://mohfw.gov.in/".to_string(),
            "https://rbi.org.in/".to_string(),
            "https://uidai.gov.in/".to_string(),

            // --- Indian Education & Research ---
            "https://ugc.ac.in/".to_string(),
            "https://nptel.ac.in/".to_string(),
            "https://icmr.nic.in/".to_string(),
            "https://csir.res.in/".to_string(),
            "https://iitd.ac.in/".to_string(),
            "https://iitb.ac.in/".to_string(),
            ],
        }
    };

    let state = Arc::new(Mutex::new(initial_state));
    
    // 2. DISK WRITER: Asynchronously save state every 10 seconds without blocking the crawler
    let saver_state = Arc::clone(&state);
    tokio::spawn(async move {
        loop {
            sleep(Duration::from_secs(10)).await;
            let s = saver_state.lock().await;
            if let Ok(json_data) = serde_json::to_string(&*s) {
                let _ = tokio::fs::write("axiom_crawler_state.json", json_data).await;
            }
        }
    });

    let bot_state = Arc::clone(&state);
    tokio::spawn(async move {
        run_autonomous_bot(bot_state).await;
    });

    let app = Router::new().route("/crawl", post(handle_manual_crawl));

    println!("[AXIOM BOT] API Gateway running on port 3000");
    let listener = tokio::net::TcpListener::bind("0.0.0.0:3000").await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

async fn run_autonomous_bot(state: Arc<Mutex<SpiderState>>) {
    println!("[AXIOM BOT] Multi-Domain Hyper-Crawler active with 50 concurrent worker threads...");

    let redis_client = redis::Client::open("redis://127.0.0.1/").expect("Redis connection failed");

    // NEW: Spawning 50 concurrent async workers to achieve extreme crawl speeds
    for worker_id in 0..50 {
        let worker_state = Arc::clone(&state);
        let r_client = redis_client.clone();

        tokio::spawn(async move {
            let mut con = r_client
                .get_multiplexed_async_connection()
                .await
                .expect("Failed to connect to Redis");

            let p_selector = Selector::parse("p").unwrap();
            let a_selector = Selector::parse("a").unwrap();
            let img_selector = Selector::parse("img").unwrap(); // NEW: Image selector

            let mut headers = reqwest::header::HeaderMap::new();
            headers.insert(
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
                    .parse()
                    .unwrap(),
            );
            headers.insert("Accept-Language", "en-US,en;q=0.9".parse().unwrap());

            let client = reqwest::Client::builder()
                .timeout(Duration::from_secs(10))
                .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
                .default_headers(headers)
                .build()
                .unwrap();

            loop {
                let current_url = {
                    let mut s = worker_state.lock().await;
                    if s.url_queue.is_empty() {
                        None
                    } else {
                        Some(s.url_queue.remove(0))
                    }
                };

                if let Some(url) = current_url {
                    let is_new = {
                        let mut s = worker_state.lock().await;
                        s.visited_urls.insert(url.clone())
                    };

                    if is_new {
                        println!("[WORKER {}] Crawling Target: {}", worker_id, url);

                        match client.get(&url).send().await {
                            Ok(response) if response.status().is_success() => {
                                if let Ok(html_content) = response.text().await {
                                    let mut new_links = Vec::new();
                                    let mut texts_to_push = Vec::new();
                                    let mut top_image = String::from("None"); // Default image

                                    // Synchronous HTML Parsing
                                    {
                                        let document = Html::parse_document(&html_content);

                                        if let Ok(base_url) = Url::parse(&url) {
                                            // NEW: Extract Top Valid Image
                                            for element in document.select(&img_selector) {
                                                if let Some(src) = element.value().attr("src") {
                                                    if let Ok(abs_url) = base_url.join(src) {
                                                        let img_url = abs_url.to_string();
                                                        let lower_url = img_url.to_lowercase();
                                                        if lower_url.contains(".jpg") || lower_url.contains(".jpeg") || lower_url.contains(".png") || lower_url.contains(".webp") {
                                                            top_image = img_url;
                                                            break; // Grab the first main valid image file
                                                        }
                                                    }
                                                }
                                            }

                                            // Extract & Filter Clean Article Links
                                            for element in document.select(&a_selector) {
                                                if let Some(href) = element.value().attr("href") {
                                                    if let Ok(mut abs_url) = base_url.join(href) {
                                                        abs_url.set_query(None);
                                                        abs_url.set_fragment(None);

                                                        let abs_str = abs_url.as_str();
                                                        if is_valid_article_url(abs_str) {
                                                            new_links.push(abs_str.to_string());
                                                        }
                                                    }
                                                }
                                            }
                                        }

                                        // Extract Clean Text Paragraphs
                                        for element in document.select(&p_selector) {
                                            let text = element.text().collect::<Vec<_>>().join(" ");
                                            if text.trim().len() > 50 {
                                                texts_to_push.push(text);
                                            }
                                        }
                                    }

                                    // Async Queue & Pipeline Push
                                    {
                                        let mut s = worker_state.lock().await;
                                        for link in new_links {
                                            if !s.visited_urls.contains(&link) {
                                                s.url_queue.push(link);
                                            }
                                        }
                                    }

                                    // NEW: Push structured JSON containing text, source_url, and image_url
                                    for text in texts_to_push {
                                        let payload = PipelinePayload {
                                            text,
                                            source_url: url.clone(),
                                            image_url: top_image.clone(),
                                        };
                                        if let Ok(json_str) = serde_json::to_string(&payload) {
                                            let _: () = con
                                                .lpush("arom_text_pipeline", json_str)
                                                .await
                                                .unwrap_or_default();
                                        }
                                    }
                                }
                            }
                            _ => {
                                // Silently drop failed fetches
                            }
                        }
                    }
                } else {
                    // Queue empty: Worker waits 2 seconds before checking again (prevents CPU lockup)
                    sleep(Duration::from_secs(2)).await;
                }
            }
        });
    }
}

async fn handle_manual_crawl(Json(payload): Json<CrawlRequest>) -> Json<Vec<CrawlResponse>> {
    let mut results = Vec::new();
    let p_selector = Selector::parse("p").unwrap();
    let client = reqwest::Client::new();

    for url in payload.target_urls {
        if let Ok(response) = client.get(&url).send().await {
            if let Ok(html) = response.text().await {
                let document = Html::parse_document(&html);
                let mut paragraphs = Vec::new();
                for element in document.select(&p_selector) {
                    let text = element.text().collect::<Vec<_>>().join(" ");
                    if text.trim().len() > 30 {
                        paragraphs.push(text.trim().to_string());
                    }
                }
                results.push(CrawlResponse {
                    url,
                    clean_paragraphs: paragraphs,
                });
            }
        }
    }
    Json(results)
}
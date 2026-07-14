import express from 'express';
import { createServer as createViteServer } from 'vite';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';
import { GoogleGenAI, Type } from '@google/genai';

dotenv.config();

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Initialize Gemini SDK with named parameters as instructed
const apiKey = process.env.GEMINI_API_KEY;
const ai = new GoogleGenAI({
  apiKey: apiKey,
  httpOptions: {
    headers: {
      'User-Agent': 'aistudio-build',
    }
  }
});

async function startServer() {
  const app = express();
  app.use(express.json({ limit: '10mb' }));

  // AI Research API endpoint
  app.post('/api/research', async (req, res) => {
    const { ticker } = req.body;
    if (!ticker) {
      return res.status(400).json({ error: 'Ticker is required' });
    }

    if (!process.env.GEMINI_API_KEY) {
      return res.status(500).json({
        error: 'GEMINI_API_KEY is not configured on the server. Please check the Secrets panel in AI Studio.'
      });
    }

    try {
      console.log(`Starting investment research for ticker: ${ticker}`);

      // Define structured schema for response
      const researchSchema = {
        type: Type.OBJECT,
        properties: {
          ticker: { type: Type.STRING },
          companyName: { type: Type.STRING },
          summary: { type: Type.STRING, description: "A high-level 2-sentence summary of the research outcome" },
          action: { type: Type.STRING, description: "Investment action recommendation: BUY, HOLD, or SELL (must be exactly one of these three in uppercase)" },
          conviction: { type: Type.STRING, description: "Conviction level: High, Medium, or Low" },
          fairValue: { type: Type.NUMBER, description: "Estimated fair value price of the stock as a positive number (e.g., 240 or 155.5)" },
          buyZone: { type: Type.STRING, description: "Recommended buy price range, e.g., '< $150' or '$130 - $145'" },
          
          // Core analysis segments
          businessModel: { type: Type.STRING, description: "Detailed explanation of how the company makes money" },
          revenueSegments: { type: Type.STRING, description: "Summary of major revenue segments with percentage breakdowns if available" },
          competitiveAdvantages: { type: Type.STRING, description: "Key competitive advantages / economic moats" },
          growthDrivers: { type: Type.STRING, description: "Key future growth drivers and secular tailwinds" },
          risks: { type: Type.STRING, description: "Major risks, competitive threats, and headwinds" },
          financialQuality: { type: Type.STRING, description: "Brief assessment of balance sheet strength, cash flow generation, and operating margins" },
          valuationAnalysis: { type: Type.STRING, description: "Brief analysis of current valuation ratios (e.g., P/E, EV/Sales, EV/EBITDA) relative to historical averages or peers" },
          
          // Full formatted document
          memoMarkdown: { type: Type.STRING, description: "A comprehensive, beautifully formatted, professional investment memo in Markdown. Should contain headers (e.g., #, ##), lists, bold text, and a summary table comparing fair value vs current price. Format it elegantly." }
        },
        required: [
          "ticker", "companyName", "summary", "action", "conviction", "fairValue", "buyZone",
          "businessModel", "revenueSegments", "competitiveAdvantages", "growthDrivers", "risks", "financialQuality", "valuationAnalysis", "memoMarkdown"
        ]
      };

      const prompt = `Perform extensive, institutional-grade investment research on the stock ticker "${ticker}".
Search reliable and up-to-date public sources (e.g., SEC filings, latest quarterly reports, news, financial databases, analyst consensus) to analyze the company's business model, recent performance, valuation, and outlook.

Ensure your analysis covers:
1. Business Model (how they make money, main value prop).
2. Revenue Segments (breakdowns with percentage if available, recent growth rates).
3. Competitive Advantages (economic moats like network effects, switching costs, cost advantages, brand).
4. Growth Drivers (short and long term triggers).
5. Major Risks (regulatory, competitive, macroeconomic).
6. Financial Quality (debt levels, cash flow conversion, margins trend).
7. Valuation (estimate a reasonable fair value and buy zone based on current multiples and future earnings growth).

Provide the final output strictly conforming to the requested JSON schema. The memoMarkdown should be extremely well-structured and written in a professional, objective investment analyst tone.`;

      // Call Gemini 3.5-flash with Search Grounding and JSON schema
      const response = await ai.models.generateContent({
        model: 'gemini-3.5-flash',
        contents: prompt,
        config: {
          tools: [{ googleSearch: {} }],
          responseMimeType: 'application/json',
          responseSchema: researchSchema,
        },
      });

      const responseText = response.text;
      if (!responseText) {
        throw new Error('Gemini returned an empty response.');
      }

      // Parse JSON response
      const resultData = JSON.parse(responseText);

      // Extract search grounding metadata sources
      const groundingChunks = response.candidates?.[0]?.groundingMetadata?.groundingChunks || [];
      const sources = groundingChunks
        .filter((chunk: any) => chunk.web?.uri)
        .map((chunk: any) => ({
          title: chunk.web.title || 'Source',
          url: chunk.web.uri
        }));

      // Return unified research result
      res.json({
        success: true,
        data: resultData,
        sources: sources
      });

    } catch (error: any) {
      console.error('Error during investment research:', error);
      res.status(500).json({
        error: error.message || 'An error occurred during the investment research process.'
      });
    }
  });

  // Serve static frontend files or run Vite middleware
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'custom',
    });
    app.use(vite.middlewares);

    app.use('*', async (req, res, next) => {
      const url = req.originalUrl;
      try {
        let template = await vite.transformIndexHtml(url, `
          <!doctype html>
          <html lang="en">
            <head>
              <meta charset="UTF-8" />
              <meta name="viewport" content="width=device-width, initial-scale=1.0" />
              <title>AI Investment Research Assistant</title>
            </head>
            <body>
              <div id="root"></div>
              <script type="module" src="/src/main.tsx"></script>
            </body>
          </html>
        `);
        res.status(200).set({ 'Content-Type': 'text/html' }).end(template);
      } catch (e) {
        vite.ssrFixStacktrace(e as Error);
        next(e);
      }
    });
  } else {
    // Serve static files in production
    app.use(express.static(path.resolve(__dirname, 'dist')));
    app.get('*', (req, res) => {
      res.sendFile(path.resolve(__dirname, 'dist', 'index.html'));
    });
  }

  const port = 3000;
  app.listen(port, '0.0.0.0', () => {
    console.log(`Full-stack server listening on http://0.0.0.0:${port}`);
  });
}

startServer();

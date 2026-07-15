/**
 * Google Workspace integration helper functions.
 * Uses standard fetch requests with the client-side OAuth access token.
 */

export interface DashboardRow {
  ticker: string;
  action: string;
  conviction: string;
  fairValue: number;
  buyZone: string;
  lastUpdated: string;
}

/**
 * Searches Google Drive for an existing "Investment Portfolio Dashboard" sheet.
 * If none is found, it creates one and initializes it with headers.
 */
export async function findOrCreateDashboardSheet(accessToken: string): Promise<{ id: string; url: string }> {
  try {
    // 1. Search for the spreadsheet file by name
    const q = encodeURIComponent("name = 'Investment Portfolio Dashboard' and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false");
    const searchRes = await fetch(`https://www.googleapis.com/drive/v3/files?q=${q}&fields=files(id,name,webViewLink)`, {
      headers: { Authorization: `Bearer ${accessToken}` }
    });

    if (!searchRes.ok) {
      throw new Error(`Failed to search Drive: ${searchRes.statusText}`);
    }

    const searchData = await searchRes.json();
    const existingFile = searchData.files?.[0];

    if (existingFile) {
      console.log('Found existing dashboard spreadsheet:', existingFile.id);
      return {
        id: existingFile.id,
        url: existingFile.webViewLink || `https://docs.google.com/spreadsheets/d/${existingFile.id}/edit`
      };
    }

    // 2. Create a new spreadsheet if not found
    console.log('Creating new dashboard spreadsheet...');
    const createRes = await fetch('https://sheets.googleapis.com/v4/spreadsheets', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        properties: {
          title: 'Investment Portfolio Dashboard'
        }
      })
    });

    if (!createRes.ok) {
      throw new Error(`Failed to create spreadsheet: ${createRes.statusText}`);
    }

    const sheetData = await createRes.json();
    const spreadsheetId = sheetData.spreadsheetId;
    const webUrl = sheetData.spreadsheetUrl || `https://docs.google.com/spreadsheets/d/${spreadsheetId}/edit`;

    // 3. Initialize headers
    console.log('Initializing spreadsheet headers...');
    const headers = ['Ticker', 'Action', 'Conviction', 'Fair Value ($)', 'Buy Zone', 'Last Updated'];
    const updateRes = await fetch(
      `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values/Sheet1!A1:F1?valueInputOption=USER_ENTERED`,
      {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          values: [headers]
        } )
      }
    );

    if (!updateRes.ok) {
      // If Sheet1 is not the default name, let's look for sheet names
      const sheets = sheetData.sheets || [];
      const firstSheetName = sheets[0]?.properties?.title || 'Sheet1';
      await fetch(
        `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values/${firstSheetName}!A1:F1?valueInputOption=USER_ENTERED`,
        {
          method: 'PUT',
          headers: {
            Authorization: `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            values: [headers]
          })
        }
      );
    }

    return { id: spreadsheetId, url: webUrl };
  } catch (error) {
    console.error('findOrCreateDashboardSheet error:', error);
    throw error;
  }
}

/**
 * Updates a row in the "Investment Portfolio Dashboard" sheet.
 * If the ticker already exists, it updates that row. Otherwise, it appends a new row.
 */
export async function updateDashboardSheetRow(
  accessToken: string,
  spreadsheetId: string,
  data: DashboardRow
): Promise<void> {
  try {
    // 1. Get current sheet values to see sheet name and find existing tickers
    // First we query spreadsheet metadata to get the first sheet's title
    const metaRes = await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}`, {
      headers: { Authorization: `Bearer ${accessToken}` }
    });

    if (!metaRes.ok) {
      throw new Error(`Failed to get sheet metadata: ${metaRes.statusText}`);
    }

    const metaData = await metaRes.json();
    const sheetName = metaData.sheets?.[0]?.properties?.title || 'Sheet1';

    // Get all values in columns A to F
    const valuesRes = await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values/${sheetName}!A:F`, {
      headers: { Authorization: `Bearer ${accessToken}` }
    });

    if (!valuesRes.ok) {
      throw new Error(`Failed to get sheet values: ${valuesRes.statusText}`);
    }

    const valuesData = await valuesRes.json();
    const rows: string[][] = valuesData.values || [];

    // Find row index (1-based index) matching the ticker
    let rowIndex = -1;
    for (let i = 1; i < rows.length; i++) {
      if (rows[i][0] && rows[i][0].trim().toUpperCase() === data.ticker.trim().toUpperCase()) {
        rowIndex = i + 1; // 1-based index
        break;
      }
    }

    const rowValues = [
      data.ticker.toUpperCase(),
      data.action,
      data.conviction,
      data.fairValue,
      data.buyZone,
      data.lastUpdated
    ];

    if (rowIndex !== -1) {
      // Overwrite existing row
      console.log(`Updating existing row ${rowIndex} for ticker ${data.ticker}`);
      const updateRes = await fetch(
        `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values/${sheetName}!A${rowIndex}:F${rowIndex}?valueInputOption=USER_ENTERED`,
        {
          method: 'PUT',
          headers: {
            Authorization: `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            values: [rowValues]
          })
        }
      );

      if (!updateRes.ok) {
        throw new Error(`Failed to update row: ${updateRes.statusText}`);
      }
    } else {
      // Append new row
      console.log(`Appending new row for ticker ${data.ticker}`);
      const appendRes = await fetch(
        `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values/${sheetName}!A1:F1:append?valueInputOption=USER_ENTERED`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            values: [rowValues]
          })
        }
      );

      if (!appendRes.ok) {
        throw new Error(`Failed to append row: ${appendRes.statusText}`);
      }
    }
  } catch (error) {
    console.error('updateDashboardSheetRow error:', error);
    throw error;
  }
}

/**
 * Creates a brand-new Google Doc memo and inserts the investment research memo.
 */
export async function createInvestmentMemoDoc(
  accessToken: string,
  ticker: string,
  companyName: string,
  memoMarkdown: string
): Promise<{ id: string; url: string }> {
  try {
    // 1. Create document
    console.log(`Creating Google Doc for ${ticker} memo...`);
    const createRes = await fetch('https://docs.googleapis.com/v1/documents', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        title: `Investment Research Memo - ${ticker} (${companyName})`
      })
    });

    if (!createRes.ok) {
      throw new Error(`Failed to create document: ${createRes.statusText}`);
    }

    const docData = await createRes.json();
    const documentId = docData.documentId;
    const webUrl = `https://docs.google.com/document/d/${documentId}/edit`;

    // 2. Insert document body text
    // Format a beautiful clean header and metadata section inside the Doc
    const dateStr = new Date().toLocaleDateString(undefined, {
      year: 'numeric', month: 'long', day: 'numeric'
    });
    const headerText = `INVESTMENT RESEARCH MEMO
----------------------------------------
TICKER: ${ticker.toUpperCase()}
COMPANY: ${companyName}
DATE: ${dateStr}
GENERATED BY: AI Investment Research Assistant
----------------------------------------

`;

    const fullText = headerText + memoMarkdown;

    console.log('Writing memo content to Google Doc...');
    const updateRes = await fetch(`https://docs.google.com/v1/documents/${documentId}:batchUpdate`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        requests: [
          {
            insertText: {
              location: { index: 1 },
              text: fullText
            }
          }
        ]
      })
    });

    if (!updateRes.ok) {
      throw new Error(`Failed to populate document: ${updateRes.statusText}`);
    }

    return { id: documentId, url: webUrl };
  } catch (error) {
    console.error('createInvestmentMemoDoc error:', error);
    throw error;
  }
}

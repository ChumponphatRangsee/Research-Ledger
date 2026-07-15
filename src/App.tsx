import { useState, useEffect } from 'react';
import { 
  TrendingUp, 
  Search, 
  FileText, 
  Database, 
  ChevronRight, 
  CheckCircle2, 
  AlertCircle, 
  LogOut, 
  ExternalLink, 
  Loader2, 
  Check, 
  ArrowUpRight, 
  Activity, 
  DollarSign, 
  ShieldAlert, 
  TrendingDown, 
  Compass, 
  Layers, 
  Sparkles,
  RefreshCw,
  FolderOpen
} from 'lucide-react';
import { User } from 'firebase/auth';
import { initAuth, googleSignIn, logout, getAccessToken } from './firebase';
import { findOrCreateDashboardSheet, updateDashboardSheetRow, createInvestmentMemoDoc } from './workspace';

interface ResearchData {
  ticker: string;
  companyName: string;
  summary: string;
  action: 'BUY' | 'HOLD' | 'SELL';
  conviction: 'High' | 'Medium' | 'Low';
  fairValue: number;
  buyZone: string;
  businessModel: string;
  revenueSegments: string;
  competitiveAdvantages: string;
  growthDrivers: string;
  risks: string;
  financialQuality: string;
  valuationAnalysis: string;
  memoMarkdown: string;
}

interface Source {
  title: string;
  url: string;
}

export default function App() {
  // Authentication states
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [authInitialized, setAuthInitialized] = useState(false);
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  // App functional states
  const [tickerInput, setTickerInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingPhase, setLoadingPhase] = useState('');
  const [researchResult, setResearchResult] = useState<ResearchData | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [activeTab, setActiveTab] = useState<'bento' | 'memo'>('bento');
  const [error, setError] = useState<string | null>(null);

  // Google Workspace connection states
  const [dashboardSheet, setDashboardSheet] = useState<{ id: string; url: string } | null>(null);
  const [checkingDashboard, setCheckingDashboard] = useState(false);
  const [sheetSyncing, setSheetSyncing] = useState(false);
  const [sheetSyncSuccess, setSheetSyncSuccess] = useState(false);
  const [docSaving, setDocSaving] = useState(false);
  const [savedDoc, setSavedDoc] = useState<{ id: string; url: string } | null>(null);

  // Custom confirmation dialog state
  const [confirmModal, setConfirmModal] = useState<{
    show: boolean;
    message: string;
    onConfirm: () => void;
  } | null>(null);

  // Recommended demo tickers
  const demoTickers = ['AAPL', 'NVDA', 'TSLA', 'AMZN', 'MSFT'];

  // 1. Initialize Auth on load
  useEffect(() => {
    const unsubscribe = initAuth(
      (currentUser, accessToken) => {
        setUser(currentUser);
        setToken(accessToken);
        setAuthInitialized(true);
        // Automatically check for or create dashboard sheet once logged in
        checkOrCreateDashboard(accessToken);
      },
      () => {
        setUser(null);
        setToken(null);
        setAuthInitialized(true);
      }
    );
    return () => unsubscribe();
  }, []);

  // Check or create Google Sheets portfolio dashboard
  const checkOrCreateDashboard = async (accessToken: string) => {
    setCheckingDashboard(true);
    try {
      const sheet = await findOrCreateDashboardSheet(accessToken);
      setDashboardSheet(sheet);
    } catch (err: any) {
      console.error('Failed to initialize investment dashboard:', err);
      setError('Could not connect to Google Drive to find your Dashboard sheet. Please check your account permissions.');
    } finally {
      setCheckingDashboard(false);
    }
  };

  const handleLogin = async () => {
    setIsLoggingIn(true);
    setError(null);
    try {
      const result = await googleSignIn();
      if (result) {
        setToken(result.accessToken);
        setUser(result.user);
        await checkOrCreateDashboard(result.accessToken);
      }
    } catch (err: any) {
      console.error('Login failed:', err);
      setError('Failed to log in with Google. Please try again.');
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
      setUser(null);
      setToken(null);
      setDashboardSheet(null);
      setResearchResult(null);
      setSources([]);
      setSavedDoc(null);
    } catch (err) {
      console.error('Logout failed:', err);
    }
  };

  // 2. Perform AI Investment Research
  const conductResearch = async (ticker: string) => {
    if (!ticker.trim()) return;
    setLoading(true);
    setError(null);
    setSavedDoc(null);
    setSheetSyncSuccess(false);

    const phases = [
      'Searching financial SEC filings, Bloomberg, and public reports...',
      'Analyzing business model, revenue splits, and product margins...',
      'Assessing core economic moats and competitive landscape...',
      'Projecting future secular tailwinds and major business risks...',
      'Evaluating cash flows, debt solvency, and quality of earnings...',
      'Running discounted cash flows (DCF) and multiple valuation formulas...',
      'Compiling and structuring full Investment Memo...'
    ];

    let phaseIndex = 0;
    setLoadingPhase(phases[0]);
    
    // Simulate natural phase transitions during research API fetch
    const phaseInterval = setInterval(() => {
      if (phaseIndex < phases.length - 1) {
        phaseIndex++;
        setLoadingPhase(phases[phaseIndex]);
      }
    }, 3500);

    try {
      const res = await fetch('/api/research', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ticker: ticker.toUpperCase().trim() }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || 'Server returned an error during research.');
      }

      const result = await res.json();
      if (result.success && result.data) {
        setResearchResult(result.data);
        setSources(result.sources || []);
      } else {
        throw new Error('Could not parse successful research data.');
      }
    } catch (err: any) {
      console.error('Research error:', err);
      setError(err.message || 'An error occurred while analyzing the stock. Please try again.');
    } finally {
      clearInterval(phaseInterval);
      setLoading(false);
      setLoadingPhase('');
    }
  };

  // 3. Save research memo as Google Doc
  const saveMemoToGoogleDocs = async () => {
    const currentToken = token || getAccessToken();
    if (!currentToken || !researchResult) return;

    setDocSaving(true);
    setError(null);
    try {
      const doc = await createInvestmentMemoDoc(
        currentToken,
        researchResult.ticker,
        researchResult.companyName,
        researchResult.memoMarkdown
      );
      setSavedDoc(doc);
    } catch (err: any) {
      console.error('Save to Google Docs failed:', err);
      setError('Could not save memo to Google Docs. Please ensure you have authorized Google Docs access.');
    } finally {
      setDocSaving(false);
    }
  };

  // 4. Sync key metrics to Google Sheets dashboard (with confirmation dialog)
  const syncToDashboardSheet = async () => {
    const currentToken = token || getAccessToken();
    if (!currentToken || !researchResult || !dashboardSheet) return;

    // MANDATORY confirmation modal before mutating data
    const tickerSymbol = researchResult.ticker.toUpperCase();
    setConfirmModal({
      show: true,
      message: `Are you sure you want to update your "Investment Portfolio Dashboard" spreadsheet with the latest analysis for ${tickerSymbol}? This will overwrite existing data for ${tickerSymbol} or append a new row.`,
      onConfirm: async () => {
        setConfirmModal(null);
        setSheetSyncing(true);
        setError(null);
        setSheetSyncSuccess(false);
        try {
          const dateStr = new Date().toLocaleString(undefined, {
            year: 'numeric', month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit'
          });

          await updateDashboardSheetRow(currentToken, dashboardSheet.id, {
            ticker: tickerSymbol,
            action: researchResult.action,
            conviction: researchResult.conviction,
            fairValue: researchResult.fairValue,
            buyZone: researchResult.buyZone,
            lastUpdated: dateStr
          });

          setSheetSyncSuccess(true);
          // Auto-hide success checkmark after 4 seconds
          setTimeout(() => setSheetSyncSuccess(false), 4000);
        } catch (err: any) {
          console.error('Sync to dashboard failed:', err);
          setError('Could not update Google Sheet. Please check spreadsheet permission and try again.');
        } finally {
          setSheetSyncing(false);
        }
      }
    });
  };

  // Simple Markdown Renderer
  const renderMarkdownText = (markdown: string) => {
    if (!markdown) return null;
    const lines = markdown.split('\n');
    return lines.map((line, idx) => {
      const trimmed = line.trim();
      if (trimmed.startsWith('# ')) {
        return <h1 key={idx} className="text-2xl font-bold text-slate-900 mt-6 mb-3 border-b border-slate-200 pb-2 id-h1">{trimmed.substring(2)}</h1>;
      }
      if (trimmed.startsWith('## ')) {
        return <h2 key={idx} className="text-xl font-bold text-slate-800 mt-5 mb-2.5 id-h2">{trimmed.substring(3)}</h2>;
      }
      if (trimmed.startsWith('### ')) {
        return <h3 key={idx} className="text-lg font-semibold text-slate-700 mt-4 mb-2 id-h3">{trimmed.substring(4)}</h3>;
      }
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        return <li key={idx} className="list-disc ml-6 my-1.5 text-slate-600 leading-relaxed id-li">{trimmed.substring(2)}</li>;
      }
      if (trimmed.startsWith('> ')) {
        return <blockquote key={idx} className="border-l-4 border-indigo-500 pl-4 py-1.5 my-3 bg-slate-50 italic text-slate-600 rounded-r-md id-quote">{trimmed.substring(2)}</blockquote>;
      }
      if (trimmed === '') {
        return <div key={idx} className="h-2.5" />;
      }
      return <p key={idx} className="text-slate-600 my-1 leading-relaxed id-p">{trimmed}</p>;
    });
  };

  // Welcome state (not logged in)
  if (!authInitialized) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col justify-center items-center p-4 id-app-loading">
        <div className="flex flex-col items-center space-y-3">
          <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
          <p className="text-sm font-medium text-slate-500">Initializing Investment Assistant...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex flex-col justify-center items-center px-4 py-12 id-login-view">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-xl border border-slate-200/80 p-8 space-y-8 text-center transition-all">
          <div className="space-y-3">
            <div className="mx-auto w-16 h-16 bg-indigo-50 rounded-2xl flex items-center justify-center border border-indigo-100 shadow-sm">
              <TrendingUp className="w-8 h-8 text-indigo-600" />
            </div>
            <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Investment Research</h1>
            <p className="text-slate-500 text-sm max-w-sm mx-auto leading-relaxed">
              Conduct professional stock research powered by Google Gemini Search Grounding. Automatically sync outputs with your customized Google Workspace.
            </p>
          </div>

          <div className="space-y-4">
            <button
              onClick={handleLogin}
              disabled={isLoggingIn}
              className="w-full flex items-center justify-center space-x-3 py-3 px-4 border border-slate-200 rounded-xl shadow-sm text-sm font-semibold text-slate-700 bg-white hover:bg-slate-50 active:bg-slate-100 transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
              id="google-signin-btn"
            >
              {isLoggingIn ? (
                <Loader2 className="w-5 h-5 text-slate-500 animate-spin" />
              ) : (
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v3.92h6.69c-.29 1.5-.14 3.08-1.03 4.22l3.27 2.53c1.92-1.77 3.03-4.38 3.03-7.6z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 24c3.24 0 5.97-1.08 7.96-2.91l-3.27-2.53c-.9.6-2.07.96-3.42.96-3.14 0-5.8-2.12-6.75-4.97L3.16 17.5C5.12 21.38 9.24 24 12 24z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.25 14.55A7.18 7.18 0 0 1 4.8 12c0-.88.15-1.74.45-2.55L1.83 6.31A11.94 11.94 0 0 0 0 12c0 2.12.55 4.12 1.5 5.88l3.75-3.33z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.96 1.19 15.24 0 12 0 9.24 0 5.12 2.62 3.16 6.5L6.91 9.83c.95-2.85 3.61-5.08 6.75-5.08z"
                  />
                </svg>
              )}
              <span>Sign in with Google</span>
            </button>

            <div className="pt-2 text-xs text-slate-400 leading-relaxed">
              Secures your workspace connections using verified Google OAuth protocols.
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 flex flex-col font-sans id-app-main">
      {/* 1. Header */}
      <header className="sticky top-0 z-30 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between shadow-sm id-header">
        <div className="flex items-center space-x-3">
          <div className="bg-indigo-600 p-2 rounded-xl text-white shadow-md shadow-indigo-200">
            <TrendingUp className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">AI Investment Research</h1>
            <p className="text-xs text-slate-500">Stock analysis with live Google search grounding</p>
          </div>
        </div>

        {/* User profile dropdown and sign out */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2.5 border-r border-slate-200 pr-4">
            {user.photoURL ? (
              <img src={user.photoURL} alt={user.displayName || 'User'} className="w-8 h-8 rounded-full border border-slate-200" />
            ) : (
              <div className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center text-indigo-700 font-bold text-sm">
                {user.displayName?.[0] || 'U'}
              </div>
            )}
            <div className="hidden md:block text-right">
              <p className="text-xs font-semibold text-slate-700 leading-none">{user.displayName}</p>
              <p className="text-[10px] text-slate-400">{user.email}</p>
            </div>
          </div>

          <button
            onClick={handleLogout}
            className="flex items-center space-x-1.5 py-1.5 px-3 rounded-lg text-xs font-semibold text-slate-600 hover:text-red-600 hover:bg-red-50 active:bg-red-100 transition-all"
            title="Sign Out"
            id="signout-btn"
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Sign Out</span>
          </button>
        </div>
      </header>

      {/* 2. Main Content Dashboard */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 id-main-grid">
        {/* LEFT COLUMN: Input & Dashboard Connections */}
        <div className="lg:col-span-4 flex flex-col space-y-6 id-left-column">
          {/* A. Search Stock Ticker Card */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5 space-y-4 id-search-card">
            <div className="flex items-center space-x-2 border-b border-slate-100 pb-3">
              <Search className="w-4 h-4 text-indigo-600" />
              <h2 className="font-bold text-slate-800 text-sm tracking-wide">RESEARCH STOCK TICKER</h2>
            </div>

            <div className="space-y-3">
              <label className="text-xs font-semibold text-slate-500 block">STOCK TICKER SYMBOL</label>
              <div className="relative">
                <input
                  type="text"
                  value={tickerInput}
                  onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
                  onKeyDown={(e) => e.key === 'Enter' && conductResearch(tickerInput)}
                  placeholder="e.g. AAPL, NVDA, TSLA"
                  className="w-full bg-slate-50 border border-slate-200 hover:border-slate-300 focus:border-indigo-500 focus:bg-white transition-all rounded-xl py-3 pl-4 pr-12 text-sm font-bold text-slate-800 uppercase placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  disabled={loading}
                />
                <button
                  onClick={() => conductResearch(tickerInput)}
                  disabled={loading || !tickerInput.trim()}
                  className="absolute right-2.5 top-2.5 p-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white transition-all disabled:opacity-40"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Quick-test rekomendasi tickers */}
            <div className="space-y-2 pt-2">
              <span className="text-[10px] font-bold text-slate-400 tracking-wider uppercase">SUGGESTED COMPANIES</span>
              <div className="flex flex-wrap gap-2">
                {demoTickers.map((t) => (
                  <button
                    key={t}
                    onClick={() => {
                      setTickerInput(t);
                      conductResearch(t);
                    }}
                    disabled={loading}
                    className="py-1 px-2.5 rounded-lg border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/50 hover:text-indigo-600 text-xs font-semibold text-slate-600 bg-white transition-all cursor-pointer"
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* B. Google Workspace Sync Panel */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5 space-y-4 id-workspace-card">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center space-x-2">
                <Database className="w-4 h-4 text-emerald-600" />
                <h2 className="font-bold text-slate-800 text-sm tracking-wide">PORTFOLIO SYNC</h2>
              </div>
              {checkingDashboard ? (
                <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />
              ) : dashboardSheet ? (
                <div className="flex items-center space-x-1 py-0.5 px-1.5 bg-emerald-50 text-emerald-700 rounded-full text-[10px] font-bold border border-emerald-100">
                  <Check className="w-3 h-3" />
                  <span>ONLINE</span>
                </div>
              ) : (
                <span className="text-[10px] font-bold text-amber-500">OFFLINE</span>
              )}
            </div>

            {checkingDashboard ? (
              <div className="py-4 text-center">
                <p className="text-xs text-slate-400 font-medium">Checking Google Sheets Dashboard...</p>
              </div>
            ) : dashboardSheet ? (
              <div className="space-y-3.5">
                <div className="p-3 bg-slate-50 border border-slate-150 rounded-xl space-y-1.5">
                  <p className="text-xs font-bold text-slate-700 flex items-center space-x-1">
                    <span>Investment Portfolio Dashboard</span>
                  </p>
                  <p className="text-[10px] text-slate-400 truncate">ID: {dashboardSheet.id}</p>
                  
                  <a
                    href={dashboardSheet.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center space-x-1 text-xs font-bold text-indigo-600 hover:text-indigo-700 mt-1 hover:underline"
                  >
                    <span>Open Portfolio Spreadsheet</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>

                {researchResult && (
                  <div className="pt-2">
                    <button
                      onClick={syncToDashboardSheet}
                      disabled={sheetSyncing}
                      className="w-full py-2.5 px-4 rounded-xl border border-transparent shadow-sm text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 transition-all flex items-center justify-center space-x-2 cursor-pointer disabled:opacity-55"
                      id="sync-dashboard-btn"
                    >
                      {sheetSyncing ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span>Updating Dashboard row...</span>
                        </>
                      ) : sheetSyncSuccess ? (
                        <>
                          <Check className="w-4 h-4" />
                          <span>Dashboard Updated!</span>
                        </>
                      ) : (
                        <>
                          <RefreshCw className="w-4 h-4" />
                          <span>Sync {researchResult.ticker} to Dashboard</span>
                        </>
                      )}
                    </button>
                    <p className="text-[10px] text-slate-400 text-center mt-1.5 leading-relaxed">
                      Saves action, conviction, fair value, and buy zone of {researchResult.ticker}.
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="py-2 text-center text-slate-500 text-xs space-y-2">
                <AlertCircle className="w-6 h-6 text-amber-500 mx-auto" />
                <p>We could not initialize the dashboard on your Google Sheets.</p>
                <button
                  onClick={() => checkOrCreateDashboard(token || '')}
                  className="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 font-bold text-xs rounded-lg transition-all"
                >
                  Retry Connection
                </button>
              </div>
            )}
          </div>

          {/* C. Source Grounding Links */}
          {researchResult && sources.length > 0 && (
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5 space-y-3.5 id-sources-card">
              <div className="flex items-center space-x-2 border-b border-slate-100 pb-2.5">
                <Compass className="w-4 h-4 text-indigo-600" />
                <h2 className="font-bold text-slate-800 text-sm tracking-wide">RELIABLE GROUNDED SOURCES</h2>
              </div>
              <p className="text-[11px] text-slate-400 leading-normal">
                Verified public financial records and market analyses retrieved during Gemini's research process:
              </p>
              <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                {sources.map((src, index) => (
                  <a
                    key={index}
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block p-2 rounded-lg bg-slate-50 border border-slate-150 hover:border-indigo-200 hover:bg-indigo-50/20 transition-all"
                  >
                    <p className="text-xs font-bold text-slate-700 truncate">{src.title}</p>
                    <p className="text-[10px] text-slate-400 flex items-center space-x-0.5 mt-0.5 truncate">
                      <span className="truncate">{src.url}</span>
                      <ArrowUpRight className="w-2.5 h-2.5 shrink-0" />
                    </p>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* RIGHT COLUMN: Active Research Outcomes / Output */}
        <div className="lg:col-span-8 flex flex-col space-y-6 id-right-column">
          {/* Active Loading Screen */}
          {loading && (
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-12 flex flex-col items-center justify-center space-y-6 min-h-[450px] id-loader">
              <div className="relative flex items-center justify-center">
                <div className="w-16 h-16 border-4 border-indigo-100 border-t-indigo-600 rounded-full animate-spin"></div>
                <Sparkles className="w-6 h-6 text-indigo-500 absolute animate-pulse" />
              </div>
              <div className="text-center space-y-2 max-w-sm">
                <h3 className="text-lg font-bold text-slate-900">Conducting Financial Analysis</h3>
                <p className="text-sm text-slate-500 leading-relaxed min-h-[40px] font-medium text-indigo-600">
                  {loadingPhase}
                </p>
                <p className="text-xs text-slate-400">
                  This takes 10-15 seconds as Gemini searches the live web and evaluates financial metrics.
                </p>
              </div>
            </div>
          )}

          {/* Active Error State */}
          {error && !loading && (
            <div className="bg-red-50 border border-red-200 rounded-2xl p-6 flex items-start space-x-4 id-error-container">
              <AlertCircle className="w-6 h-6 text-red-600 shrink-0 mt-0.5" />
              <div className="space-y-1.5">
                <h4 className="font-bold text-red-800 text-sm">Error Occurred</h4>
                <p className="text-xs text-red-600 leading-relaxed">{error}</p>
              </div>
            </div>
          )}

          {/* Blank slate (no research conducted yet) */}
          {!researchResult && !loading && !error && (
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-12 flex flex-col items-center justify-center text-center space-y-5 min-h-[450px] id-blank-slate">
              <div className="w-16 h-16 bg-slate-50 rounded-2xl flex items-center justify-center border border-slate-100 shadow-inner">
                <FileText className="w-8 h-8 text-slate-400" />
              </div>
              <div className="space-y-1.5 max-w-md">
                <h3 className="text-lg font-bold text-slate-950">No Research Performed</h3>
                <p className="text-sm text-slate-500 leading-relaxed">
                  Enter a stock ticker symbol (e.g. <b>AAPL</b> for Apple, <b>NVDA</b> for NVIDIA) in the panel on the left to pull live search data and perform full analysis.
                </p>
              </div>
            </div>
          )}

          {/* A. Investment Metrics Header Summary */}
          {researchResult && !loading && (
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-5 id-metrics-summary">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-2xl font-extrabold text-slate-900 tracking-tight">{researchResult.ticker}</span>
                    <span className="text-sm font-semibold text-slate-500 bg-slate-100 py-0.5 px-2 rounded-md">{researchResult.companyName}</span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">Institutional Investment Grade Summary Outcomes</p>
                </div>

                <div className="flex flex-wrap gap-4 items-center">
                  <div className="py-1 px-3.5 rounded-xl border border-slate-200 flex items-center space-x-2">
                    <span className="text-[10px] font-bold text-slate-400 tracking-wider uppercase">Recommendation</span>
                    <span className={`text-xs font-black tracking-widest rounded-lg px-2.5 py-1 ${
                      researchResult.action === 'BUY' ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' :
                      researchResult.action === 'HOLD' ? 'bg-amber-50 text-amber-700 border border-amber-100' :
                      'bg-red-50 text-red-700 border border-red-100'
                    }`}>
                      {researchResult.action}
                    </span>
                  </div>

                  <div className="py-1 px-3.5 rounded-xl border border-slate-200 flex items-center space-x-2">
                    <span className="text-[10px] font-bold text-slate-400 tracking-wider uppercase">Conviction</span>
                    <span className="text-xs font-extrabold text-slate-700 bg-slate-50 border border-slate-150 px-2 py-1 rounded-lg">
                      {researchResult.conviction}
                    </span>
                  </div>
                </div>
              </div>

              {/* Grid values */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 border-t border-slate-100 pt-4">
                <div className="p-3.5 bg-indigo-50/30 rounded-xl border border-indigo-100/50">
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Estimated Fair Value</p>
                  <p className="text-2xl font-black text-indigo-900 mt-0.5">${researchResult.fairValue.toFixed(2)}</p>
                </div>

                <div className="p-3.5 bg-emerald-50/30 rounded-xl border border-emerald-100/50">
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Target Buy Zone</p>
                  <p className="text-2xl font-black text-emerald-900 mt-0.5">{researchResult.buyZone}</p>
                </div>

                <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-150">
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Valuation Quality</p>
                  <p className="text-sm font-bold text-slate-700 mt-1.5 truncate">Based on Multiples & Growth</p>
                </div>
              </div>

              <div className="p-4 bg-slate-50/70 border border-slate-200/50 rounded-xl">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">EXECUTIVE BRIEF SUMMARY</p>
                <p className="text-xs text-slate-600 leading-relaxed mt-1">{researchResult.summary}</p>
              </div>
            </div>
          )}

          {/* B. Tab Layout Content Panel */}
          {researchResult && !loading && (
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 flex flex-col overflow-hidden id-content-tabs">
              {/* Tab Selector bar */}
              <div className="bg-slate-50 border-b border-slate-200 px-6 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex space-x-2">
                  <button
                    onClick={() => setActiveTab('bento')}
                    className={`py-1.5 px-4 rounded-lg text-xs font-bold transition-all ${
                      activeTab === 'bento' 
                        ? 'bg-indigo-600 text-white shadow-sm' 
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    Business Analysis Bento
                  </button>
                  <button
                    onClick={() => setActiveTab('memo')}
                    className={`py-1.5 px-4 rounded-lg text-xs font-bold transition-all ${
                      activeTab === 'memo' 
                        ? 'bg-indigo-600 text-white shadow-sm' 
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    Investment Memo Preview
                  </button>
                </div>

                {/* Docs Action panel */}
                <div className="flex items-center">
                  {savedDoc ? (
                    <a
                      href={savedDoc.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="py-1.5 px-3.5 bg-indigo-50 border border-indigo-200 text-indigo-700 hover:bg-indigo-100 transition-all rounded-lg text-xs font-bold flex items-center space-x-1.5"
                    >
                      <FolderOpen className="w-3.5 h-3.5" />
                      <span>Open Document</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  ) : (
                    <button
                      onClick={saveMemoToGoogleDocs}
                      disabled={docSaving}
                      className="py-1.5 px-3.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 transition-all text-white rounded-lg text-xs font-bold flex items-center space-x-1.5 cursor-pointer disabled:opacity-55"
                      id="save-docs-btn"
                    >
                      {docSaving ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Generating Google Doc...</span>
                        </>
                      ) : (
                        <>
                          <FileText className="w-3.5 h-3.5" />
                          <span>Save Memo to Google Docs</span>
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>

              {/* Tab Display Panel */}
              <div className="p-6 id-tab-body">
                {activeTab === 'bento' ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5 id-bento-grid">
                    {/* 1. Business Model */}
                    <div className="p-4 rounded-xl border border-slate-200 hover:border-indigo-100 transition-all space-y-2 bg-slate-50/10">
                      <div className="flex items-center space-x-2 text-indigo-600">
                        <Activity className="w-4 h-4" />
                        <h4 className="text-xs font-bold tracking-wider uppercase">Business Model & Monetization</h4>
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed">{researchResult.businessModel}</p>
                    </div>

                    {/* 2. Revenue Segments */}
                    <div className="p-4 rounded-xl border border-slate-200 hover:border-indigo-100 transition-all space-y-2 bg-slate-50/10">
                      <div className="flex items-center space-x-2 text-indigo-600">
                        <Layers className="w-4 h-4" />
                        <h4 className="text-xs font-bold tracking-wider uppercase">Major Revenue Splits</h4>
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed">{researchResult.revenueSegments}</p>
                    </div>

                    {/* 3. Competitive Advantages */}
                    <div className="p-4 rounded-xl border border-slate-200 hover:border-emerald-100 transition-all space-y-2 bg-slate-50/10">
                      <div className="flex items-center space-x-2 text-emerald-600">
                        <CheckCircle2 className="w-4 h-4" />
                        <h4 className="text-xs font-bold tracking-wider uppercase">Competitive Advantages (Moats)</h4>
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed">{researchResult.competitiveAdvantages}</p>
                    </div>

                    {/* 4. Growth Drivers */}
                    <div className="p-4 rounded-xl border border-slate-200 hover:border-emerald-100 transition-all space-y-2 bg-slate-50/10">
                      <div className="flex items-center space-x-2 text-emerald-600">
                        <TrendingUp className="w-4 h-4" />
                        <h4 className="text-xs font-bold tracking-wider uppercase">Growth Drivers & Tailwinds</h4>
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed">{researchResult.growthDrivers}</p>
                    </div>

                    {/* 5. Major Risks */}
                    <div className="p-4 rounded-xl border border-slate-200 hover:border-red-100 transition-all space-y-2 bg-slate-50/10">
                      <div className="flex items-center space-x-2 text-red-500">
                        <ShieldAlert className="w-4 h-4" />
                        <h4 className="text-xs font-bold tracking-wider uppercase">Risks, Threats, & Headwinds</h4>
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed">{researchResult.risks}</p>
                    </div>

                    {/* 6. Financial Quality */}
                    <div className="p-4 rounded-xl border border-slate-200 hover:border-amber-100 transition-all space-y-2 bg-slate-50/10">
                      <div className="flex items-center space-x-2 text-amber-600">
                        <DollarSign className="w-4 h-4" />
                        <h4 className="text-xs font-bold tracking-wider uppercase">Financial Quality Assessment</h4>
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed">{researchResult.financialQuality}</p>
                    </div>

                    {/* 7. Valuation Analysis (Full span) */}
                    <div className="md:col-span-2 p-4 rounded-xl border border-slate-200 hover:border-indigo-100 transition-all space-y-2 bg-slate-50/10">
                      <div className="flex items-center space-x-2 text-indigo-600">
                        <TrendingDown className="w-4 h-4" />
                        <h4 className="text-xs font-bold tracking-wider uppercase">Current Valuation & Valuation Logic</h4>
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed">{researchResult.valuationAnalysis}</p>
                    </div>
                  </div>
                ) : (
                  <div className="prose max-w-none text-slate-700 bg-slate-50/40 p-4 rounded-xl border border-slate-100 max-h-[600px] overflow-y-auto font-serif">
                    {renderMarkdownText(researchResult.memoMarkdown)}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* 3. Footer */}
      <footer className="bg-white border-t border-slate-200 py-4 px-6 text-center text-xs text-slate-400 mt-auto id-footer">
        <p>© 2026 AI Investment Research Assistant. All rights reserved with permission.</p>
      </footer>

      {/* 4. Confirmation Dialog Modal (Destructive / Mutation Confirmation as mandated) */}
      {confirmModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/40 flex items-center justify-center p-4 backdrop-blur-sm id-confirm-modal">
          <div className="relative bg-white rounded-2xl max-w-md w-full shadow-2xl border border-slate-200/80 p-6 space-y-5">
            <div className="flex items-center space-x-3 text-emerald-600 border-b border-slate-100 pb-3">
              <Database className="w-5 h-5 shrink-0" />
              <h3 className="font-bold text-slate-900">Confirm Dashboard Sync</h3>
            </div>
            
            <p className="text-xs text-slate-600 leading-relaxed">
              {confirmModal.message}
            </p>

            <div className="flex justify-end space-x-3 pt-2">
              <button
                onClick={() => setConfirmModal(null)}
                className="py-1.5 px-4 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs cursor-pointer transition-all"
              >
                Cancel
              </button>
              <button
                onClick={confirmModal.onConfirm}
                className="py-1.5 px-4 rounded-lg bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white font-bold text-xs cursor-pointer transition-all"
              >
                Confirm Sync
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import { useState } from "react";
import "./App.css";

type View = "customer" | "support";

function App() {
  const [view, setView] = useState<View>("customer");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [token, setToken] = useState("");
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<
    { sender: "customer" | "agent"; text: string }[]
  >([
    {
      sender: "agent",
      text: "Welcome to Rubies MFB! I'm your virtual banking assistant. How can I help you today?",
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [otpRequested, setOtpRequested] = useState(false);
  const [developmentOtp, setDevelopmentOtp] = useState("");

  const API_URL = "http://127.0.0.1:8000";
  const AGENT_URL = "http://127.0.0.1:8001";

  async function requestOtp() {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_URL}/api/auth/request-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone_number: phone }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Unable to request a verification code.");
      }

      setOtpRequested(true);
      setDevelopmentOtp(data.development_otp || "");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not connect to the Banking API.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function verifyOtp() {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_URL}/api/auth/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone_number: phone, otp }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Verification failed.");
      }

      setToken(data.access_token);
      setAuthenticated(true);
      setDevelopmentOtp("");
      setMessages([
        {
          sender: "agent",
          text: "You're connected! I'm your Rubies MFB virtual assistant. What can I help you with today?",
        },
      ]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not verify the code.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function sendMessage() {
    const text = message.trim();

    if (!text || !token || loading) return;

    setMessages((current) => [...current, { sender: "customer", text }]);
    setMessage("");
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${AGENT_URL}/api/agent`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message: text }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(
          data.detail || `The assistant returned HTTP ${response.status}.`,
        );
      }

      const contentType = response.headers.get("content-type") || "";

      if (contentType.includes("text/event-stream")) {
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let answer = "";

        if (reader) {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const events = buffer.split("\n\n");
            buffer = events.pop() || "";

            for (const event of events) {
              const dataLine = event
                .split("\n")
                .find((line) => line.startsWith("data:"));

              if (!dataLine) continue;

              try {
                const payload = JSON.parse(dataLine.slice(5).trim());
                const extracted =
                  payload.delta?.content ??
                  payload.content ??
                  payload.text ??
                  payload.message;

                if (typeof extracted === "string") answer += extracted;
              } catch {
                // Ignore non-JSON SSE events.
              }
            }
          }
        }

        setMessages((current) => [
          ...current,
          {
            sender: "agent",
            text: answer || "The assistant completed the request without a text response.",
          },
        ]);
      } else {
        const data = await response.json();
        const answer =
          data.message ||
          data.response ||
          data.answer ||
          data.content ||
          JSON.stringify(data);

        setMessages((current) => [
          ...current,
          { sender: "agent", text: String(answer) },
        ]);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to reach the virtual assistant.",
      );
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    setAuthenticated(false);
    setToken("");
    setOtp("");
    setOtpRequested(false);
    setDevelopmentOtp("");
    setMessages([
      {
        sender: "agent",
        text: "Welcome to Rubies MFB! I'm your virtual banking assistant. How can I help you today?",
      },
    ]);
    setView("customer");
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">R</div>
          <div>
            <h1>rubies</h1>
            <span>MICROFINANCE BANK</span>
          </div>
        </div>

        <div className="workspace-label">WORKSPACE</div>

        <button
          className={`nav-item ${view === "customer" ? "active" : ""}`}
          onClick={() => setView("customer")}
        >
          <span className="nav-icon">◉</span>
          Customer experience
        </button>

        <button
          className={`nav-item ${view === "support" ? "active" : ""}`}
          onClick={() => setView("support")}
        >
          <span className="nav-icon">▤</span>
          Support desk
          <span className="nav-badge">DEMO</span>
        </button>

        <div className="sidebar-bottom">
          <div className="status-dot" />
          <div>
            <strong>Development environment</strong>
            <span>Rubies MFB Agent</span>
          </div>
        </div>
      </aside>

      <section className="main-panel">
        <header className="topbar">
          <div>
            <span className="breadcrumb">Workspace / </span>
            <strong>
              {view === "customer" ? "Customer experience" : "Support desk"}
            </strong>
          </div>
          <div className="topbar-right">
            <span className="environment-pill">
              <span className="status-dot" />
              LOCAL DEMO
            </span>
            {authenticated && (
              <button className="logout-button" onClick={logout}>
                Sign out
              </button>
            )}
            <div className="avatar">{authenticated ? "C" : "R"}</div>
          </div>
        </header>

        {view === "customer" ? (
          <div className="content">
            <div className="page-heading">
              <div>
                <span className="eyebrow">RUBIES DIGITAL BANKING</span>
                <h2>Your banking, made simpler.</h2>
                <p>
                  Get account assistance, transaction support, and answers
                  whenever you need them.
                </p>
              </div>
              <div className="heading-decoration">R.</div>
            </div>

            {!authenticated ? (
              <div className="login-layout">
                <div className="welcome-card">
                  <div className="welcome-icon">✳</div>
                  <span className="eyebrow">HERE FOR YOU</span>
                  <h3>Banking support that puts you first.</h3>
                  <p>
                    Sign in securely with your registered phone number to
                    speak with our virtual banking assistant.
                  </p>
                  <div className="feature-line">
                    <span>✓</span> Secure phone verification
                  </div>
                  <div className="feature-line">
                    <span>✓</span> Intelligent customer assistance
                  </div>
                  <div className="feature-line">
                    <span>✓</span> Human support when you need it
                  </div>
                  <div className="welcome-footer">
                    RUBIES MFB <span>•</span> CUSTOMER CARE
                  </div>
                </div>

                <div className="login-card">
                  <span className="eyebrow">CUSTOMER ACCESS</span>
                  <h3>Welcome back</h3>
                  <p className="muted">
                    {otpRequested
                      ? "Enter the six-digit code to continue."
                      : "Enter your registered phone number to get started."}
                  </p>

                  <label htmlFor="phone">Phone number</label>
                  <input
                    id="phone"
                    type="tel"
                    autoComplete="tel"
                    placeholder="e.g. 08012345678"
                    value={phone}
                    disabled={otpRequested || loading}
                    onChange={(event) => setPhone(event.target.value)}
                  />

                  {otpRequested && (
                    <>
                      <label htmlFor="otp">Verification code</label>
                      <input
                        id="otp"
                        inputMode="numeric"
                        autoComplete="one-time-code"
                        maxLength={6}
                        placeholder="Enter 6-digit code"
                        value={otp}
                        onChange={(event) =>
                          setOtp(event.target.value.replace(/\D/g, ""))
                        }
                      />
                    </>
                  )}

                  {developmentOtp && (
                    <div className="dev-code">
                      <span>Development OTP</span>
                      <strong>{developmentOtp}</strong>
                      <button onClick={() => setOtp(developmentOtp)}>
                        Use code
                      </button>
                    </div>
                  )}

                  {error && <div className="error-message">{error}</div>}

                  {!otpRequested ? (
                    <button
                      className="primary-button"
                      onClick={requestOtp}
                      disabled={loading || phone.trim().length < 7}
                    >
                      {loading ? "Requesting code..." : "Send verification code →"}
                    </button>
                  ) : (
                    <>
                      <button
                        className="primary-button"
                        onClick={verifyOtp}
                        disabled={loading || otp.length !== 6}
                      >
                        {loading ? "Verifying..." : "Verify and continue →"}
                      </button>
                      <button
                        className="text-button"
                        onClick={() => {
                          setOtpRequested(false);
                          setOtp("");
                          setDevelopmentOtp("");
                          setError("");
                        }}
                      >
                        Use a different phone number
                      </button>
                    </>
                  )}

                  <div className="security-note">
                    <span>▣</span>
                    Your session is protected with token-based authentication.
                  </div>
                </div>
              </div>
            ) : (
              <div className="chat-layout">
                <div className="chat-card">
                  <div className="chat-header">
                    <div className="assistant-avatar">R</div>
                    <div>
                      <h3>Rubies Virtual Assistant</h3>
                      <span>
                        <span className="status-dot" /> Online · Banking support
                      </span>
                    </div>
                    <span className="secure-label">SECURE SESSION</span>
                  </div>

                  <div className="chat-messages">
                    <div className="date-divider">TODAY</div>
                    {messages.map((item, index) => (
                      <div
                        key={`${index}-${item.sender}`}
                        className={`message-row ${item.sender}`}
                      >
                        {item.sender === "agent" && (
                          <div className="message-avatar">R</div>
                        )}
                        <div className="message-bubble">
                          <span className="message-author">
                            {item.sender === "agent" ? "Rubies Assistant" : "You"}
                          </span>
                          <p>{item.text}</p>
                        </div>
                      </div>
                    ))}
                    {loading && (
                      <div className="typing-indicator">
                        <span />
                        <span />
                        <span />
                        <small>Assistant is thinking...</small>
                      </div>
                    )}
                  </div>

                  {error && <div className="chat-error">{error}</div>}

                  <form
                    className="chat-composer"
                    onSubmit={(event) => {
                      event.preventDefault();
                      void sendMessage();
                    }}
                  >
                    <input
                      aria-label="Message"
                      placeholder="Ask about your banking..."
                      value={message}
                      onChange={(event) => setMessage(event.target.value)}
                      disabled={loading}
                    />
                    <button
                      type="submit"
                      disabled={loading || !message.trim()}
                      aria-label="Send message"
                    >
                      ↑
                    </button>
                  </form>
                  <div className="composer-caption">
                    Please don't share your PIN or password in chat.
                  </div>
                </div>

                <aside className="help-card">
                  <span className="eyebrow">QUICK HELP</span>
                  <h3>What can I help with?</h3>
                  {[
                    ["↗", "Transactions", "Payments and transfers"],
                    ["▤", "Account enquiries", "General banking questions"],
                    ["◎", "Loan enquiries", "Eligibility and loan support"],
                    ["↗", "Human support", "Get help from our team"],
                  ].map(([icon, title, description]) => (
                    <button
                      className="help-option"
                      key={title}
                      onClick={() => {
                        setMessage(
                          title === "Human support"
                            ? "I'd like to speak with a human support representative."
                            : `I need help with ${title.toLowerCase()}.`,
                        );
                      }}
                    >
                      <span className="help-icon">{icon}</span>
                      <span>
                        <strong>{title}</strong>
                        <small>{description}</small>
                      </span>
                      <span className="help-arrow">›</span>
                    </button>
                  ))}
                  <div className="privacy-card">
                    <strong>🔒 Your privacy matters</strong>
                    <p>
                      Your banking requests are handled through an authenticated
                      session.
                    </p>
                  </div>
                </aside>
              </div>
            )}
          </div>
        ) : (
          <div className="content support-content">
            <div className="page-heading">
              <div>
                <span className="eyebrow">OPERATIONS</span>
                <h2>Customer support desk</h2>
                <p>
                  A workspace for human representatives to manage escalated
                  customer conversations.
                </p>
              </div>
            </div>

            <div className="support-notice">
              <div className="notice-icon">i</div>
              <div>
                <strong>Support desk interface — next integration step</strong>
                <p>
                  The layout is ready, but live handoff queues and agent replies
                  still need to be connected to the Banking API support-handoff
                  endpoints. This view does not yet display real customer cases.
                </p>
              </div>
            </div>

            <div className="support-stats">
              <div className="stat-card">
                <span>OPEN CASES</span>
                <strong>—</strong>
                <small>Awaiting queue connection</small>
              </div>
              <div className="stat-card">
                <span>IN PROGRESS</span>
                <strong>—</strong>
                <small>Awaiting queue connection</small>
              </div>
              <div className="stat-card">
                <span>RESOLVED TODAY</span>
                <strong>—</strong>
                <small>Awaiting queue connection</small>
              </div>
            </div>

            <div className="empty-support">
              <div className="empty-icon">▤</div>
              <h3>Your support queue will appear here</h3>
              <p>
                We'll connect this screen to the existing support-handoff
                lifecycle so representatives can review case summaries, respond,
                and resolve conversations.
              </p>
              <button
                className="secondary-button"
                onClick={() => setView("customer")}
              >
                Return to customer experience
              </button>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}

export default App;

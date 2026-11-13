
import { useState } from "react";
import "./SupportDesk.css";

type SupportDeskProps = {
  apiUrl: string;
};

type Dispute = {
  case_reference: string;
  customer_id: number;
  customer_reference: string;
  customer_name: string;
  transaction_id: string | null;
  category: string;
  description: string;
  status: string;
  created_at: string;
  updated_at: string;
};

type Handoff = {
  reference: string;
  customer_id: number;
  customer_reference: string;
  customer_name: string;
  status: string;
  priority: string;
  route: string;
  reason: string;
  summary: string;
  actions_attempted: string[] | string | null;
  unresolved_questions: string[] | string | null;
  correlation_id: string | null;
  failure_reason: string | null;
  acknowledgement_reference: string | null;
  created_at: string;
  updated_at: string;
  acknowledged_at: string | null;
};

type PaginatedResponse<T> = {
  items: T[];
  limit: number;
  offset: number;
};
type DemoSupportProfile = {
  id: string;
  name: string;
  phone: string;
  account: string;
};

type ActiveTab = "disputes" | "handoffs";

const PAGE_SIZE = 20;

const DEMO_SUPPORT_PROFILES: DemoSupportProfile[] = [
  {
    id: "DEMO-SUPPORT-001",
    name: "Demo Support Staff",
    phone: "08000000009",
    account: "9000000001",
  },
];

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleString("en-NG", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatLabel(value: string | null | undefined): string {
  if (!value) return "—";

  return value
    .replace(/[_-]/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function renderDetail(value: string[] | string | null | undefined) {
  if (value == null || value === "") return "—";

  if (Array.isArray(value)) {
    if (value.length === 0) return "—";

    return (
      <ul className="sd-detail-list">
        {value.map((item, index) => (
          <li key={`${item}-${index}`}>{item}</li>
        ))}
      </ul>
    );
  }

  return value;
}

function StatusBadge({ value }: { value: string }) {
  const normalized = value.toLowerCase().replace(/[_\s]/g, "-");

  return (
    <span className={`sd-status-badge ${normalized}`}>
      {formatLabel(value)}
    </span>
  );
}

function SupportDesk({ apiUrl }: SupportDeskProps) {
  const [phoneNumber, setPhoneNumber] = useState("");
  const [otp, setOtp] = useState("");
  const [otpRequested, setOtpRequested] = useState(false);
  const [developmentOtp, setDevelopmentOtp] = useState("");
  const [staffToken, setStaffToken] = useState("");

  const [activeTab, setActiveTab] = useState<ActiveTab>("disputes");
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [handoffs, setHandoffs] = useState<Handoff[]>([]);

  const [disputesOffset, setDisputesOffset] = useState(0);
  const [handoffsOffset, setHandoffsOffset] = useState(0);
  const [disputesHasMore, setDisputesHasMore] = useState(false);
  const [handoffsHasMore, setHandoffsHasMore] = useState(false);

  const [loading, setLoading] = useState(false);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [error, setError] = useState("");
  const [logsError, setLogsError] = useState("");

  const baseUrl = apiUrl.replace(/\/+$/, "");

  async function requestOtp() {
    if (!phoneNumber.trim() || loading) return;

    setLoading(true);
    setError("");
    setDevelopmentOtp("");

    try {
      const response = await fetch(
        `${baseUrl}/api/support-staff/auth/request-otp`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            phone_number: phoneNumber.trim(),
          }),
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to request a verification code."
        );
      }

      setOtpRequested(true);
      setDevelopmentOtp(data.development_otp || "");
      setOtp("");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not connect to the Banking API."
      );
    } finally {
      setLoading(false);
    }
  }

  async function verifyOtp() {
    if (otp.length !== 6 || loading) return;

    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${baseUrl}/api/support-staff/auth/verify-otp`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            phone_number: phoneNumber.trim(),
            otp,
          }),
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail || "Staff verification failed.");
      }

      if (!data.access_token) {
        throw new Error(
          "Authentication succeeded without an access token."
        );
      }

      setStaffToken(data.access_token);
      setOtp("");
      setDevelopmentOtp("");

      await loadLogs(data.access_token, "disputes", 0);
      await loadLogs(data.access_token, "handoffs", 0);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to verify the staff code."
      );
    } finally {
      setLoading(false);
    }
  }

  async function loadLogs(
    accessToken: string,
    logType: ActiveTab,
    offset: number
  ) {
    setLoadingLogs(true);
    setLogsError("");

    const endpoint =
      logType === "disputes" ? "disputes" : "handoffs";

    try {
      const response = await fetch(
        `${baseUrl}/api/support-desk/${endpoint}?limit=${PAGE_SIZE}&offset=${offset}`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        if (response.status === 401) {
          setStaffToken("");
          setDisputes([]);
          setHandoffs([]);
          throw new Error(
            "Your staff session is invalid or has expired. Please sign in again."
          );
        }

        throw new Error(
          data.detail || `Unable to load ${endpoint}.`
        );
      }

      const result = data as PaginatedResponse<
        Dispute | Handoff
      >;

      if (!Array.isArray(result.items)) {
        throw new Error(
          `The ${endpoint} endpoint returned an unexpected response.`
        );
      }

      if (logType === "disputes") {
        setDisputes(result.items as Dispute[]);
        setDisputesOffset(offset);
        setDisputesHasMore(result.items.length === PAGE_SIZE);
      } else {
        setHandoffs(result.items as Handoff[]);
        setHandoffsOffset(offset);
        setHandoffsHasMore(result.items.length === PAGE_SIZE);
      }
    } catch (err) {
      setLogsError(
        err instanceof Error
          ? err.message
          : "Unable to retrieve Support Desk records."
      );
    } finally {
      setLoadingLogs(false);
    }
  }

  function refreshCurrentLog() {
    if (!staffToken) return;

    const offset =
      activeTab === "disputes"
        ? disputesOffset
        : handoffsOffset;

    void loadLogs(staffToken, activeTab, offset);
  }

  function changePage(direction: "previous" | "next") {
    if (!staffToken || loadingLogs) return;

    const currentOffset =
      activeTab === "disputes"
        ? disputesOffset
        : handoffsOffset;

    const hasMore =
      activeTab === "disputes"
        ? disputesHasMore
        : handoffsHasMore;

    const nextOffset =
      direction === "next"
        ? currentOffset + PAGE_SIZE
        : Math.max(0, currentOffset - PAGE_SIZE);

    if (direction === "next" && !hasMore) return;
    if (direction === "previous" && currentOffset === 0) return;

    void loadLogs(staffToken, activeTab, nextOffset);
  }

  function signOut() {
    setStaffToken("");
    setPhoneNumber("");
    setOtp("");
    setOtpRequested(false);
    setDevelopmentOtp("");

    setDisputes([]);
    setHandoffs([]);

    setDisputesOffset(0);
    setHandoffsOffset(0);
    setDisputesHasMore(false);
    setHandoffsHasMore(false);

    setError("");
    setLogsError("");
    setActiveTab("disputes");
  }

  const currentCount =
    activeTab === "disputes"
      ? disputes.length
      : handoffs.length;

  const currentOffset =
    activeTab === "disputes"
      ? disputesOffset
      : handoffsOffset;

  const currentHasMore =
    activeTab === "disputes"
      ? disputesHasMore
      : handoffsHasMore;

  const currentRecords =
    activeTab === "disputes" ? disputes : handoffs;

  if (!staffToken) {
    return (
      <div className="content support-content">
        <div className="page-heading">
          <div>
            <span className="eyebrow">OPERATIONS / STAFF ACCESS</span>
            <h2>Customer support desk</h2>
            <p>
              Secure staff access to customer disputes and human
              support handoff records.
            </p>
          </div>
        </div>

        <div className="sd-login-layout">
          <section className="sd-welcome-panel">
            <div className="sd-welcome-icon">R</div>

            <span className="eyebrow">SUPPORT OPERATIONS</span>

            <h3>Customer support, with visibility.</h3>

            <p>
              Review customer-confirmed disputes and conversations
              escalated by the virtual assistant.
            </p>

            <div className="sd-feature">
              <span>✓</span>
              Disputes register
            </div>

            <div className="sd-feature">
              <span>✓</span>
              Human support handoff register
            </div>

            <div className="sd-feature">
              <span>✓</span>
              Secure staff authentication
            </div>

            <div className="sd-welcome-footer">
              RUBIES MFB · INTERNAL SUPPORT
            </div>
          </section>

          <section className="sd-login-card">
            <span className="eyebrow">STAFF ACCESS</span>
            <h3>Staff sign in</h3>

            <p className="sd-muted">
              {otpRequested
                ? "Enter the six-digit verification code sent to your registered phone number."
                : "Enter your registered staff phone number to request a verification code."}
            </p>

            <label htmlFor="support-phone">Phone number</label>

            <input
              id="support-phone"
              type="tel"
              autoComplete="tel"
              placeholder="Enter registered staff phone number"
              value={phoneNumber}
              disabled={otpRequested || loading}
              onChange={(event) =>
                setPhoneNumber(event.target.value)
              }
            />

            {!otpRequested && (
              <div className="sd-demo-profiles">
                <span>Quick fill:</span>
                {DEMO_SUPPORT_PROFILES.map((profile) => (
                  <button
                    key={profile.id}
                    type="button"
                    className="sd-demo-profile-button"
                    disabled={loading}
                    onClick={() => {
                      setPhoneNumber(profile.phone);
                      setError("");
                    }}
                  >
                    {profile.name}
                  </button>
                ))}
              </div>
            )}

            {otpRequested && (
              <>
                <label htmlFor="support-otp">
                  Verification code
                </label>

                <input
                  id="support-otp"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  placeholder="Enter 6-digit code"
                  value={otp}
                  onChange={(event) =>
                    setOtp(
                      event.target.value.replace(/\D/g, "")
                    )
                  }
                />
              </>
            )}

            {developmentOtp && (
              <div className="sd-development-otp">
                <span>Development OTP</span>
                <strong>{developmentOtp}</strong>

                <button
                  type="button"
                  onClick={() => setOtp(developmentOtp)}
                >
                  Use code
                </button>
              </div>
            )}

            {error && (
              <div className="sd-error" role="alert">
                {error}
              </div>
            )}

            {!otpRequested ? (
              <button
                type="button"
                className="sd-primary-button"
                onClick={() => void requestOtp()}
                disabled={
                  loading || phoneNumber.trim().length < 7
                }
              >
                {loading
                  ? "Requesting code..."
                  : "Request verification code →"}
              </button>
            ) : (
              <>
                <button
                  type="button"
                  className="sd-primary-button"
                  onClick={() => void verifyOtp()}
                  disabled={loading || otp.length !== 6}
                >
                  {loading
                    ? "Verifying..."
                    : "Verify and sign in →"}
                </button>

                <button
                  type="button"
                  className="sd-text-button"
                  disabled={loading}
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

            <div className="sd-security-note">
              <span>▣</span>
              Staff-only access. Customer authentication credentials
              cannot be used to access this workspace.
            </div>
          </section>
        </div>
      </div>
    );
  }

  return (
    <div className="content support-content">
      <div className="page-heading sd-page-heading">
        <div>
          <span className="eyebrow">OPERATIONS / SUPPORT RECORDS</span>
          <h2>Customer support desk</h2>
          <p>
            Read-only visibility into disputes and customer
            conversations escalated by the virtual assistant.
          </p>
        </div>

        <button
          type="button"
          className="sd-refresh-button"
          onClick={refreshCurrentLog}
          disabled={loadingLogs}
        >
          {loadingLogs ? "Refreshing..." : "↻ Refresh"}
        </button>
      </div>

      <div className="sd-session-banner">
        <div className="sd-session-indicator">
          <span className="status-dot" />
          <div>
            <strong>Authenticated staff session</strong>
            <small>Support Desk access is active</small>
          </div>
        </div>

        <button
          type="button"
          className="sd-signout-button"
          onClick={signOut}
        >
          Sign out
        </button>
      </div>

      <div className="sd-log-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "disputes"}
          className={activeTab === "disputes" ? "active" : ""}
          onClick={() => {
            setActiveTab("disputes");
            setLogsError("");
            if (disputes.length === 0) {
              void loadLogs(staffToken, "disputes", 0);
            }
          }}
        >
          <span className="sd-tab-icon">▤</span>
          Disputes log
          <span className="sd-tab-count">{disputes.length}</span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "handoffs"}
          className={activeTab === "handoffs" ? "active" : ""}
          onClick={() => {
            setActiveTab("handoffs");
            setLogsError("");
            if (handoffs.length === 0) {
              void loadLogs(staffToken, "handoffs", 0);
            }
          }}
        >
          <span className="sd-tab-icon">↗</span>
          Human handoffs
          <span className="sd-tab-count">{handoffs.length}</span>
        </button>
      </div>

      <div className="sd-log-heading">
        <div>
          <span className="eyebrow">
            {activeTab === "disputes"
              ? "CUSTOMER DISPUTES"
              : "ESCALATED CONVERSATIONS"}
          </span>

          <h3>
            {activeTab === "disputes"
              ? "Disputes register"
              : "Human support handoffs"}
          </h3>

          <p>
            {activeTab === "disputes"
              ? "Disputes confirmed by customers and recorded by the virtual assistant."
              : "Conversations escalated by the virtual assistant for human attention."}
          </p>
        </div>

        <span className="sd-record-count">
          {currentCount} records on this page
        </span>
      </div>

      {logsError && (
        <div className="sd-error sd-log-error" role="alert">
          {logsError}
        </div>
      )}

      {loadingLogs && currentRecords.length === 0 ? (
        <div className="sd-loading">
          <span className="sd-spinner" />
          <strong>Loading support records...</strong>
          <p>Retrieving records from the Banking API.</p>
        </div>
      ) : currentCount === 0 ? (
        <div className="sd-empty-state">
          <div className="sd-empty-icon">
            {activeTab === "disputes" ? "▤" : "↗"}
          </div>

          <h3>
            {activeTab === "disputes"
              ? "No disputes recorded"
              : "No human handoffs recorded"}
          </h3>

          <p>
            {activeTab === "disputes"
              ? "Customer-confirmed disputes will appear here when the virtual assistant records them."
              : "Customer conversations escalated to human support will appear here."}
          </p>

          <button
            type="button"
            className="sd-secondary-button"
            onClick={refreshCurrentLog}
            disabled={loadingLogs}
          >
            Refresh records
          </button>
        </div>
      ) : (
        <>
          {activeTab === "disputes" ? (
            <div className="sd-record-list">
              {disputes.map((dispute) => (
                <article
                  className="sd-record-card"
                  key={dispute.case_reference}
                >
                  <div className="sd-record-card-header">
                    <div>
                      <span className="sd-record-reference">
                        {dispute.case_reference}
                      </span>
                      <h4>{dispute.customer_name}</h4>
                      <small>{dispute.customer_reference}</small>
                    </div>

                    <StatusBadge value={dispute.status} />
                  </div>

                  <div className="sd-record-grid">
                    <div>
                      <span>Category</span>
                      <strong>{formatLabel(dispute.category)}</strong>
                    </div>

                    <div>
                      <span>Transaction ID</span>
                      <strong>{dispute.transaction_id || "—"}</strong>
                    </div>

                    <div>
                      <span>Customer ID</span>
                      <strong>{dispute.customer_id}</strong>
                    </div>

                    <div>
                      <span>Recorded</span>
                      <strong>{formatDate(dispute.created_at)}</strong>
                    </div>
                  </div>

                  <div className="sd-record-description">
                    <span>Dispute description</span>
                    <p>{dispute.description || "No description provided."}</p>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="sd-record-list">
              {handoffs.map((handoff) => (
                <article
                  className="sd-record-card"
                  key={handoff.reference}
                >
                  <div className="sd-record-card-header">
                    <div>
                      <span className="sd-record-reference">
                        {handoff.reference}
                      </span>
                      <h4>{handoff.customer_name}</h4>
                      <small>{handoff.customer_reference}</small>
                    </div>

                    <StatusBadge value={handoff.status} />
                  </div>

                  <div className="sd-record-grid">
                    <div>
                      <span>Priority</span>
                      <strong>
                        {formatLabel(handoff.priority)}
                      </strong>
                    </div>

                    <div>
                      <span>Route</span>
                      <strong>{formatLabel(handoff.route)}</strong>
                    </div>

                    <div>
                      <span>Customer ID</span>
                      <strong>{handoff.customer_id}</strong>
                    </div>

                    <div>
                      <span>Recorded</span>
                      <strong>{formatDate(handoff.created_at)}</strong>
                    </div>
                  </div>

                  <div className="sd-record-description">
                    <span>Reason for escalation</span>
                    <p>{handoff.reason || "—"}</p>
                  </div>

                  <div className="sd-record-description">
                    <span>Conversation summary</span>
                    <p>{handoff.summary || "—"}</p>
                  </div>

                  <div className="sd-handoff-details">
                    <details>
                      <summary>View additional handoff details</summary>

                      <div className="sd-detail-section">
                        <span>Actions attempted</span>
                        <div>
                          {renderDetail(handoff.actions_attempted)}
                        </div>
                      </div>

                      <div className="sd-detail-section">
                        <span>Unresolved questions</span>
                        <div>
                          {renderDetail(handoff.unresolved_questions)}
                        </div>
                      </div>

                      {handoff.failure_reason && (
                        <div className="sd-detail-section">
                          <span>Failure reason</span>
                          <p>{handoff.failure_reason}</p>
                        </div>
                      )}

                      {handoff.acknowledgement_reference && (
                        <div className="sd-detail-section">
                          <span>Acknowledgement reference</span>
                          <strong>
                            {handoff.acknowledgement_reference}
                          </strong>
                        </div>
                      )}

                      {handoff.correlation_id && (
                        <div className="sd-detail-section">
                          <span>Correlation ID</span>
                          <code>{handoff.correlation_id}</code>
                        </div>
                      )}

                      <div className="sd-detail-section">
                        <span>Last updated</span>
                        <strong>{formatDate(handoff.updated_at)}</strong>
                      </div>

                      <div className="sd-detail-section">
                        <span>Acknowledged at</span>
                        <strong>
                          {formatDate(handoff.acknowledged_at)}
                        </strong>
                      </div>
                    </details>
                  </div>
                </article>
              ))}
            </div>
          )}

          <div className="sd-pagination">
            <span>
              Showing {currentOffset + 1}–
              {currentOffset + currentCount}
            </span>

            <div>
              <button
                type="button"
                className="sd-page-button"
                disabled={currentOffset === 0 || loadingLogs}
                onClick={() => changePage("previous")}
              >
                ← Previous
              </button>

              <button
                type="button"
                className="sd-page-button"
                disabled={!currentHasMore || loadingLogs}
                onClick={() => changePage("next")}
              >
                Next →
              </button>
            </div>
          </div>
        </>
      )}

      <div className="sd-readonly-note">
        <span>ⓘ</span>
        <p>
          These registers provide read-only visibility. Dispute
          investigation and human support follow-up take place
          outside this agent workflow.
        </p>
      </div>
    </div>
  );
}

export default SupportDesk;

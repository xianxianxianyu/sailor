export type ViewId = "discover" | "feeds" | "kb" | "follow";

type NavItem = { id: ViewId; icon: string; label: string };

const NAV_ITEMS: NavItem[] = [
  { id: "discover", icon: "🔍", label: "发现" },
  { id: "feeds", icon: "📡", label: "订阅源" },
  { id: "kb", icon: "📚", label: "知识库" },
  { id: "follow", icon: "📬", label: "追踪" },
];

type Props = {
  active: ViewId;
  onChange: (id: ViewId) => void;
  onSettingsClick: () => void;
};

export default function NavBar({ active, onChange, onSettingsClick }: Props) {
  return (
    <nav className="nav-bar" role="navigation" aria-label="主导航">
      {NAV_ITEMS.map((item) => (
        <button
          key={item.id}
          className={`nav-item ${active === item.id ? "nav-active" : ""}`}
          onClick={() => onChange(item.id)}
          aria-current={active === item.id ? "page" : undefined}
          title={item.label}
        >
          <span className="nav-icon">{item.icon}</span>
          <span className="nav-label">{item.label}</span>
        </button>
      ))}

      <button
        className="nav-item nav-settings"
        onClick={onSettingsClick}
        title="模型配置"
      >
        <span className="nav-icon">⚙</span>
        <span className="nav-label">配置</span>
      </button>
    </nav>
  );
}

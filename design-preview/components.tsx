import { Bell, BookOpen, ChartNoAxesColumnIncreasing, ChevronRight, Flame, House, Layers, UserRound } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import male from '../docs/design/approved-v5/assets/welcome-male.png';
import female from '../docs/design/approved-v5/assets/welcome-female.png';
import robot from '../docs/design/approved-v5/assets/mascot-robot-directions.png';

export type Gender = 'male' | 'female' | null;
export const NAV: { id: string; label: string; icon: LucideIcon; path: string }[] = [
  { id: 'home', label: 'Trang chủ', icon: House, path: '/' },
  { id: 'learning', label: 'Học tập', icon: BookOpen, path: '/luyen-tap' },
  { id: 'cards', label: 'Thẻ ôn tập', icon: Layers, path: '/luyen-tap/bo-the' },
  { id: 'progress', label: 'Tiến độ', icon: ChartNoAxesColumnIncreasing, path: '/tien-do' },
  { id: 'profile', label: 'Profile', icon: UserRound, path: '/profile' },
];

export function BrandHeader({ streak = 12 }: { streak?: number }) {
  return <header className="brand-header">
    <div className="status-bar" aria-hidden="true"><span>9:41</span><span className="status-signals"><i/><i/><i/><b/></span></div>
    <div className="brand-row"><div className="brand"><strong>DocPrep</strong><span>Ôn thi YHDP</span></div>
      <div className="brand-actions"><span className="streak-badge" aria-label={`${streak} ngày ôn liên tiếp`}><Flame size={15} strokeWidth={1.8}/><span>{streak}</span></span><span className="bell" aria-label="Thông báo"><Bell size={22} strokeWidth={1.7}/><i/></span></div>
    </div>
  </header>;
}

export function Greeting({ gender, name = 'Minh An', compact = false }: { gender: Gender; name?: string; compact?: boolean }) {
  const src = gender === 'male' ? male : gender === 'female' ? female : null;
  return <section className={`greeting ${compact ? 'compact' : ''} ${!src ? 'neutral' : ''}`} aria-label="Lời chào">
    <div className="greeting-copy"><span>Chào buổi sáng,</span><h1>{name || 'bạn'}</h1><p>Học từng chút, vững kiến thức hơn.</p></div>
    {src && <img src={src} alt="" className="greeting-art"/>}
  </section>;
}

export function FlashcardSummary({ due = 8, onStart }: { due?: number; onStart?: () => void }) {
  return <section className="flashcard-summary"><div className="flashcard-heading"><span className="flat-icon"><Layers size={25} strokeWidth={1.65}/></span><div><h2>Thẻ ôn tập</h2><p className="due-count">{due} thẻ đến hạn</p></div></div>
    <p className="supporting">Ôn lại để nhớ lâu hơn.</p><button className="primary" onClick={onStart}>{due ? 'Ôn thẻ ngay' : 'Xem bộ thẻ'}</button>
  </section>;
}

export function BottomNavigation({ active = 'home' }: { active?: string }) {
  return <nav className="bottom-navigation" aria-label="Bố cục điều hướng"><div className="nav-items">{NAV.map(({ id, label, icon: Icon }) => <span key={id} className={active === id ? 'nav-item active' : 'nav-item'} aria-current={active === id ? 'page' : undefined}><Icon size={21} strokeWidth={1.7}/><span>{label}</span></span>)}</div><span className="home-indicator" aria-hidden="true"/></nav>;
}

export function RobotLauncher({ onOpen }: { onOpen?: () => void }) {
  return <button className="robot-launcher" onClick={onOpen} aria-label="Mở Gia sư AI"><span className="robot-image" style={{ backgroundImage: `url(${robot})` }}/><span className="ai-label">AI</span></button>;
}

export function ListRow({ icon: Icon, title, detail, meta }: { icon: LucideIcon; title: string; detail?: string; meta?: string }) {
  return <div className="list-row"><Icon size={20} strokeWidth={1.7}/><div className="row-copy"><span>{title}</span>{detail && <small>{detail}</small>}</div>{meta && <small className="row-meta">{meta}</small>}<ChevronRight size={16} strokeWidth={1.7}/></div>;
}

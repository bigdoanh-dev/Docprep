import React, { useState, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { Bell, BookOpen, Check, ChevronRight, Layers, LogOut, Palette, Play, ShieldCheck, Target, X } from 'lucide-react';
import '@fontsource/be-vietnam-pro/400.css';
import '@fontsource/be-vietnam-pro/500.css';
import '@fontsource/be-vietnam-pro/600.css';
import { BrandHeader, Greeting, FlashcardSummary, BottomNavigation, RobotLauncher, ListRow, type Gender } from './components';
import './styles.css';

function Device({ children, active, label, robot = false, onRobot }: { children: ReactNode; active: string; label: string; robot?: boolean; onRobot?: () => void }) {
  return <article className="device-column"><div className="device"><BrandHeader/><div className="main-surface"><div className="screen-content">{children}</div><BottomNavigation active={active}/></div>{robot && <RobotLauncher onOpen={onRobot}/>}</div><p className="device-caption">{label}</p></article>;
}

function Home({ gender, name, onReview, onRobot }: { gender: Gender; name: string; onReview: () => void; onRobot: () => void }) {
  return <Device active="home" label={gender === 'male' ? 'Trang chủ · Nam' : gender === 'female' ? 'Trang chủ · Nữ' : 'Trang chủ · Chưa chọn'} robot onRobot={onRobot}>
    <Greeting gender={gender} name={name}/><FlashcardSummary onStart={onReview}/>
    <section className="today-section"><div className="section-heading"><h2>Phiên học hôm nay</h2><span>Xem phiên <ChevronRight size={14}/></span></div><div className="today-list"><ListRow icon={Layers} title="Ôn thẻ đến hạn" meta="8 thẻ"/><ListRow icon={Target} title="Luyện điểm yếu" meta="5 câu"/><ListRow icon={Play} title="Học tiếp" meta="1 bài"/></div></section>
    <section className="continue-section"><div className="section-heading"><h2>Tiếp tục học</h2></div><ListRow icon={BookOpen} title="Dịch tễ học cơ bản" detail="Tiếp tục bài đang học"/></section>
  </Device>;
}

function Profile({ onSave, onRobot }: { onSave: (name: string, gender: Gender) => void; onRobot: () => void }) {
  const [name, setName] = useState('Minh An'), [gender, setGender] = useState<Gender>('female'), [saved, setSaved] = useState(false);
  return <Device active="profile" label="Profile · Chọn hình chào theo giới tính">
    <div className="profile-heading"><h1>Profile</h1><p>Thiết lập của bạn</p></div>
    <form className="profile-form" onSubmit={e => { e.preventDefault(); onSave(name.trim(), gender); setSaved(true); }}>
      <label className="field">Tên hiển thị<input value={name} required maxLength={80} onChange={e => { setName(e.target.value); setSaved(false); }}/></label>
      <fieldset><legend>Giới tính</legend><div className="gender-control">{([{ value: 'male', label: 'Nam' }, { value: 'female', label: 'Nữ' }, { value: null, label: 'Chưa chọn' }] as const).map(v => <button key={v.label} type="button" aria-pressed={gender === v.value} className={gender === v.value ? 'selected' : ''} onClick={() => { setGender(v.value); setSaved(false); }}>{v.label}</button>)}</div></fieldset>
      <p className="field-help">Minh họa lời chào theo lựa chọn của bạn.</p><Greeting gender={gender} name={name} compact/>
      <button className="primary" type="submit">{saved ? <><Check size={16}/>Đã lưu thay đổi</> : 'Lưu thay đổi'}</button>
    </form>
    <div className="profile-links"><button className="link-button" onClick={onRobot}><ListRow icon={Palette} title="Bạn đồng hành AI" meta="Robot"/></button><ListRow icon={Bell} title="Thông báo nhắc học"/><ListRow icon={ShieldCheck} title="Quyền dữ liệu và đồng thuận"/><ListRow icon={LogOut} title="Đăng xuất"/></div>
  </Device>;
}

function App() {
  const [profile, setProfile] = useState<{ name: string; gender: Gender }>({ name: 'Minh An', gender: 'female' });
  const [dialog, setDialog] = useState<'review' | 'robot' | null>(null), [revealed, setRevealed] = useState(false);
  return <main className="preview-page"><header className="preview-heading"><div><h1>DocPrep YHDP</h1><p>Bản chốt giao diện V6</p></div><p className="preview-note">Chữ và icon dựng bằng code · Dữ liệu minh họa</p></header>
    <div className="device-grid"><Home gender="male" name={profile.name} onReview={() => { setDialog('review'); setRevealed(false); }} onRobot={() => setDialog('robot')}/><Home gender={profile.gender} name={profile.name} onReview={() => { setDialog('review'); setRevealed(false); }} onRobot={() => setDialog('robot')}/><Profile onSave={(name, gender) => setProfile({ name, gender })} onRobot={() => setDialog('robot')}/></div>
    {dialog && <div className="dialog-backdrop" onClick={() => setDialog(null)}><section className="preview-dialog" role="dialog" aria-modal="true" aria-label={dialog === 'review' ? 'Mẫu thẻ ôn tập' : 'Robot Gia sư AI'} onClick={e => e.stopPropagation()}><button className="close-dialog" aria-label="Đóng" onClick={() => setDialog(null)}><X size={20}/></button><h2>{dialog === 'review' ? 'Thẻ ôn tập' : 'Gia sư AI'}</h2><p>{dialog === 'review' ? revealed ? 'Đáp án và nguồn sẽ hiện tại đây sau khi lật thẻ.' : 'Mặt trước của thẻ ôn tập' : 'Robot là nhân vật mặc định. Phiên hỏi đáp và bộ chọn nhân vật sẽ dùng luồng đã chốt.'}</p>{dialog === 'review' && <button className="primary" onClick={() => setRevealed(!revealed)}>{revealed ? 'Xem mặt trước' : 'Hiện đáp án'}</button>}<small>Bản xem thiết kế, chưa kết nối dữ liệu học.</small></section></div>}
  </main>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);

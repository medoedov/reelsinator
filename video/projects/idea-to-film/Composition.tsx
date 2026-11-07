import React from "react";
import { AbsoluteFill, Sequence, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { EASE, Reveal } from "../../src/ui/Panel";
import config from "./project.json";

const C = config.colors;
const progress = (frame: number, start: number, length = 22) => interpolate(frame, [start, start + length], [0, 1], EASE);
const stage = { width: 1280, height: 720 };

const Header: React.FC<{ index: number; label: string; light?: boolean }> = ({ index, label, light = false }) => (
  <div style={{ position: "absolute", left: 66, top: 42, right: 66, display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 16, fontWeight: 700, letterSpacing: "0.14em", color: light ? C.background : C.muted }}>
    <span>REELINATOR <span style={{ paddingLeft: 16, opacity: 0.42 }}> / </span> <span style={{ paddingLeft: 16 }}>STUDIO NOTES</span></span>
    <span>{String(index).padStart(2, "0")} <span style={{ opacity: 0.45 }}> / </span> {label}</span>
  </div>
);

const Footer: React.FC<{ label: string; light?: boolean }> = ({ label, light = false }) => (
  <div style={{ position: "absolute", left: 66, right: 66, bottom: 38, display: "flex", justifyContent: "space-between", fontSize: 15, color: light ? C.background : C.muted }}>
    <span>{label}</span><span>ОДНА МЫСЛЬ. МНОГО ВОЗМОЖНОСТЕЙ.</span>
  </div>
);

const Line: React.FC<{ children: React.ReactNode; delay: number; size?: number }> = ({ children, delay, size = 88 }) => {
  const frame = useCurrentFrame();
  return <Reveal progress={progress(frame, delay)} size={size} pad={0.2}><div style={{ fontSize: size, fontWeight: 700, lineHeight: 1.03, letterSpacing: "-0.065em" }}>{children}</div></Reveal>;
};

const Idea = () => {
  const f = useCurrentFrame();
  const reveal = progress(f, 4, 36);
  const orbit = f * 0.006;
  return (
    <AbsoluteFill style={{ background: C.background }}>
      <Header index={1} label="МЫСЛЬ" />
      <div style={{ position: "absolute", left: 66, top: 177 }}>
        <div style={{ color: C.muted, fontSize: 19, marginBottom: 22 }}>Любое видео начинается просто.</div>
        <Line delay={3}>Сначала —</Line>
        <Line delay={10}>одна мысль.</Line>
        <div style={{ marginTop: 34, fontSize: 22, color: C.muted, opacity: progress(f, 32) }}>Её ещё нельзя увидеть.<br />Но уже хочется рассказать.</div>
      </div>
      <svg width={580} height={580} viewBox="0 0 580 580" style={{ position: "absolute", right: 15, top: 87, overflow: "visible" }}>
        <circle cx={290} cy={290} r={242} fill="none" stroke={C.foreground} strokeOpacity={0.08} />
        <circle cx={290} cy={290} r={181} fill="none" stroke={C.foreground} strokeOpacity={0.12} />
        <g transform={`translate(290 290) rotate(${f * 0.18})`}>
          <ellipse rx={243} ry={104} fill="none" stroke={C.accent} strokeWidth={1.3} strokeOpacity={reveal * 0.8} />
          <ellipse rx={243} ry={104} transform="rotate(62)" fill="none" stroke={C.accent} strokeWidth={1.3} strokeOpacity={reveal * 0.5} />
          <ellipse rx={243} ry={104} transform="rotate(-62)" fill="none" stroke={C.accent} strokeWidth={1.3} strokeOpacity={reveal * 0.5} />
        </g>
        {[0, 1, 2, 3, 4, 5].map((i) => {
          const angle = i * Math.PI / 3 + orbit;
          const r = 181 + (1 - reveal) * 120;
          const x = 290 + Math.cos(angle) * r;
          const y = 290 + Math.sin(angle) * r;
          return <g key={i} opacity={progress(f, i * 3)}><line x1={290} y1={290} x2={x} y2={y} stroke={C.accent} strokeOpacity={0.23} /><circle cx={x} cy={y} r={i === 0 ? 12 : 7} fill={i % 2 ? C.foreground : C.accent} /></g>;
        })}
        <circle cx={290} cy={290} r={80 * reveal} fill={C.accent} />
        <circle cx={290} cy={290} r={89 + Math.sin(f / 14) * 4} fill="none" stroke={C.accent} strokeOpacity={0.26} strokeWidth={2} />
        <text x={290} y={299} fill={C.foreground} fontSize={28} fontWeight={700} textAnchor="middle" opacity={progress(f, 22)}>идея</text>
      </svg>
      <Footer label="01 — Сформулировать главное" />
    </AbsoluteFill>
  );
};

const Story = () => {
  const f = useCurrentFrame();
  const cards = [
    { label: "Зацепить", sub: "С чего всё началось", number: "01" },
    { label: "Раскрыть", sub: "Что меняется дальше", number: "02" },
    { label: "Оставить", sub: "Какую мысль унести", number: "03" },
  ];
  return (
    <AbsoluteFill style={{ background: C.foreground, color: C.background }}>
      <Header index={2} label="СЦЕНЫ" light />
      <div style={{ position: "absolute", left: 66, top: 119 }}><Line delay={2} size={70}>Мысль обретает форму.</Line></div>
      <div style={{ position: "absolute", left: 66, top: 253, display: "flex", gap: 24 }}>
        {cards.map((card, i) => {
          const p = progress(f, 14 + i * 13, 28);
          const lift = Math.sin((f - i * 12) / 34) * 3;
          return <div key={card.number} style={{ width: 366, height: 298, padding: 27, boxSizing: "border-box", borderRadius: 16, background: i === 1 ? C.accent : "#e5e0d7", color: i === 1 ? C.foreground : C.background, transform: `translateY(${(1 - p) * 170 + lift}px) rotate(${(1 - p) * (i - 1) * 9}deg)`, opacity: p }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 15, fontWeight: 700 }}><span>СЦЕНА {card.number}</span><span>↗</span></div>
            <svg width={290} height={105} viewBox="0 0 290 105" style={{ marginTop: 17, overflow: "visible" }}>
              {i === 0 ? <><circle cx={145} cy={52} r={36} stroke="currentColor" strokeWidth={2} fill="none" /><circle cx={145} cy={52} r={7 + progress(f, 27) * 10} fill="currentColor" /><path d="M84 52H107M183 52H206M145 0V15M145 88V104" stroke="currentColor" strokeWidth={2} /></> : null}
              {i === 1 ? [0, 1, 2, 3, 4].map((bar) => <rect key={bar} x={65 + bar * 35} y={88 - (22 + bar * 13) * progress(f, 38 + bar * 3)} width={22} height={(22 + bar * 13) * progress(f, 38 + bar * 3)} rx={4} fill="currentColor" opacity={0.5 + bar * 0.12} />) : null}
              {i === 2 ? <><path d="M89 53L129 83L198 21" fill="none" stroke="currentColor" strokeWidth={10} strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - progress(f, 62, 35)} /></> : null}
            </svg>
            <div style={{ fontSize: 35, fontWeight: 700, letterSpacing: "-0.04em", marginTop: 12 }}>{card.label}</div>
            <div style={{ fontSize: 18, marginTop: 8, opacity: 0.74 }}>{card.sub}</div>
          </div>;
        })}
      </div>
      <Footer label="02 — Найти логику истории" light />
    </AbsoluteFill>
  );
};

const Edit = () => {
  const f = useCurrentFrame();
  const line = progress(f, 32, 94);
  return (
    <AbsoluteFill style={{ background: C.background }}>
      <Header index={3} label="МОНТАЖ" />
      <div style={{ position: "absolute", left: 66, top: 115 }}>
        <Line delay={2} size={70}>Теперь — поймать ритм.</Line>
        <div style={{ fontSize: 22, color: C.muted, marginTop: 19, opacity: progress(f, 16) }}>Соединить. Убрать лишнее. Дать важному время.</div>
      </div>
      <div style={{ position: "absolute", top: 288, left: 66, width: 1148, height: 273, background: "#1b2335", border: "1px solid #303a50", borderRadius: 16, overflow: "hidden" }}>
        <div style={{ height: 38, borderBottom: "1px solid #303a50", color: C.muted, fontSize: 13, display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0 24px" }}><span>ТАЙМЛАЙН / 18 СЕКУНД</span><span>00:00:{String(Math.floor(line * 18)).padStart(2, "0")}</span></div>
        <div style={{ position: "absolute", left: 105, top: 47, right: 25, display: "flex", justifyContent: "space-between", fontSize: 12, color: C.muted }}>{[0, 3, 6, 9, 12, 15, 18].map((s) => <span key={s}>{String(s).padStart(2, "0")}с</span>)}</div>
        <div style={{ position: "absolute", left: 21, top: 97, color: C.muted, fontSize: 12 }}>СЦЕНЫ</div>
        <div style={{ position: "absolute", left: 21, top: 179, color: C.muted, fontSize: 12 }}>ТЕКСТ</div>
        {[0, 1, 2, 3].map((i) => {
          const p = progress(f, 10 + i * 10, 28);
          return <div key={i} style={{ position: "absolute", left: 106 + i * 252 + (1 - p) * (90 - i * 60), top: 78 - (1 - p) * 60, width: 242, height: 65, borderRadius: 7, background: i % 2 ? C.accent : "#b6c6fd", color: i % 2 ? C.foreground : C.background, opacity: p, display: "flex", alignItems: "center", gap: 18, paddingLeft: 18, boxSizing: "border-box", fontSize: 17, fontWeight: 700 }}><span style={{ opacity: 0.65, fontSize: 13 }}>0{i + 1}</span>{["Мысль", "История", "Ритм", "Результат"][i]}</div>;
        })}
        {[0, 1, 2, 3, 4, 5].map((i) => <div key={i} style={{ position: "absolute", left: 106 + i * 168, top: 163, height: 37, width: 140 + (i % 2) * 12, borderRadius: 5, background: "#49536b", opacity: progress(f, 46 + i * 5), display: "flex", alignItems: "center", paddingLeft: 13, fontSize: 12, color: C.foreground }}>{["Одна мысль", "Найти форму", "Начало", "Развитие", "Собрать ритм", "Готово"][i]}</div>)}
        <div style={{ position: "absolute", left: 106, top: 224, width: 998, height: 2, background: "#333e56" }}><div style={{ width: `${line * 100}%`, height: "100%", background: C.accent }} /></div>
        <div style={{ position: "absolute", left: 106 + line * 998, top: 40, height: 180, width: 2, background: C.foreground }}><div style={{ position: "absolute", left: -5, top: 0, width: 12, height: 10, background: C.foreground, borderRadius: "0 0 4px 4px" }} /></div>
      </div>
      <Footer label="03 — Собрать движение во времени" />
    </AbsoluteFill>
  );
};

const Result = () => {
  const f = useCurrentFrame();
  const p = progress(f, 4, 35);
  return (
    <AbsoluteFill style={{ background: C.accent }}>
      <Header index={4} label="РЕЗУЛЬТАТ" />
      <div style={{ position: "absolute", left: 66, top: 166 }}>
        <Line delay={3} size={96}>Идея стала</Line>
        <Line delay={11} size={96}>видео.</Line>
        <div style={{ fontSize: 24, lineHeight: 1.4, marginTop: 31, opacity: progress(f, 35) }}>Готово к просмотру.<br />Открыто для правок.</div>
      </div>
      <div style={{ position: "absolute", right: 89, top: 184, width: 430, height: 285, borderRadius: 22, background: C.foreground, color: C.background, transform: `translateY(${(1 - p) * 95}px) rotate(${(1 - p) * 8 - 3}deg)`, opacity: p, boxShadow: "0 30px 60px rgba(12, 26, 79, 0.25)", overflow: "hidden" }}>
        <div style={{ padding: "24px 27px", fontSize: 15, fontWeight: 700, display: "flex", justifyContent: "space-between" }}><span>ТВОЯ ИСТОРИЯ</span><span>18″</span></div>
        <svg width={100} height={100} viewBox="0 0 100 100" style={{ position: "absolute", left: 165, top: 90 }}><circle cx={50} cy={50} r={48} fill={C.accent} /><path d="M42 30L70 50L42 70Z" fill={C.foreground} /></svg>
        <div style={{ position: "absolute", left: 27, right: 27, bottom: 29, height: 4, background: "#dad6cf", borderRadius: 2 }}><div style={{ width: `${progress(f, 23, 60) * 100}%`, height: 4, background: C.accent, borderRadius: 2 }} /></div>
      </div>
      <div style={{ position: "absolute", right: 85, top: 507, fontSize: 17, display: "flex", alignItems: "center", gap: 11, opacity: progress(f, 52) }}><span style={{ width: 8, height: 8, borderRadius: 8, background: C.foreground }} />Проект остаётся редактируемым</div>
      <Footer label="04 — Сохранить результат и возможности" />
    </AbsoluteFill>
  );
};

export const Film = () => {
  const { width, height } = useVideoConfig();
  const scale = Math.min(width / stage.width, height / stage.height);
  return (
    <AbsoluteFill style={{ background: C.background, color: C.foreground, fontFamily: config.fontFamily }}>
      <div style={{ position: "absolute", width: stage.width, height: stage.height, left: (width - stage.width * scale) / 2, top: (height - stage.height * scale) / 2, transform: `scale(${scale})`, transformOrigin: "0 0" }}>
        <Sequence durationInFrames={120}><Idea /></Sequence>
        <Sequence from={120} durationInFrames={150}><Story /></Sequence>
        <Sequence from={270} durationInFrames={150}><Edit /></Sequence>
        <Sequence from={420} durationInFrames={120}><Result /></Sequence>
      </div>
    </AbsoluteFill>
  );
};

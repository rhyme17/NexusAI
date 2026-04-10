interface RoleRadarChartProps {
  items: Array<[string, number]>;
  isChinese: boolean;
}

export function RoleRadarChart({ items, isChinese }: RoleRadarChartProps) {
  if (items.length === 0) {
    return <p className="text-sm text-[#6b6860]">{isChinese ? "暂无角色数据。" : "No role data yet."}</p>;
  }

  const topItems = items.slice(0, 6);
  const maxValue = Math.max(...topItems.map((item) => item[1]), 1);
  const centerX = 150;
  const centerY = 120;
  const radius = 85;
  const angleStep = (Math.PI * 2) / topItems.length;

  const points = topItems
    .map(([_, value], index) => {
      const ratio = value / maxValue;
      const angle = -Math.PI / 2 + index * angleStep;
      const x = centerX + Math.cos(angle) * radius * ratio;
      const y = centerY + Math.sin(angle) * radius * ratio;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="rounded-2xl border border-[#ddd7ca] bg-[#fffcf6] p-3">
      <svg viewBox="0 0 300 240" className="h-[240px] w-full" role="img" aria-label={isChinese ? "角色分布雷达图" : "Role distribution radar chart"}>
        {[0.25, 0.5, 0.75, 1].map((ratio) => {
          const ringPoints = topItems
            .map((_, index) => {
              const angle = -Math.PI / 2 + index * angleStep;
              const x = centerX + Math.cos(angle) * radius * ratio;
              const y = centerY + Math.sin(angle) * radius * ratio;
              return `${x},${y}`;
            })
            .join(" ");
          return <polygon key={ratio} points={ringPoints} fill="none" stroke="#e2dbcc" strokeWidth="1" />;
        })}

        {topItems.map(([role], index) => {
          const angle = -Math.PI / 2 + index * angleStep;
          const x = centerX + Math.cos(angle) * radius;
          const y = centerY + Math.sin(angle) * radius;
          const labelX = centerX + Math.cos(angle) * (radius + 20);
          const labelY = centerY + Math.sin(angle) * (radius + 20);
          return (
            <g key={role}>
              <line x1={centerX} y1={centerY} x2={x} y2={y} stroke="#e2dbcc" strokeWidth="1" />
              <text x={labelX} y={labelY} textAnchor="middle" className="fill-[#6b6860] text-[10px]">
                {role}
              </text>
            </g>
          );
        })}

        <polygon points={points} fill="rgba(217,119,87,0.22)" stroke="#d97757" strokeWidth="2" />
      </svg>
      <p className="text-xs text-[#8a867d]">{isChinese ? `已按角色数量归一化（最大值 ${maxValue}）` : `Normalized by role count (max ${maxValue})`}</p>
    </div>
  );
}


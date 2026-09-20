import { DataBanner, NoData } from "@/components/DataBanner";
import { SettingsPanel } from "@/components/SettingsPanel";
import { SubscribePanel } from "@/components/SubscribePanel";
import { getMeta, hasData } from "@/lib/data";
import { longDate } from "@/lib/format";
import { SITE_NAME } from "@/lib/copy";

export const metadata = {
  title: `Settings — ${SITE_NAME}`,
  description: "Appearance, your account, what this site keeps, and where the data comes from.",
};

export default function SettingsPage() {
  if (!hasData()) return <NoData />;
  const meta = getMeta();

  return (
    <div className="page stack" style={{ gap: "var(--gap-lg)" }}>
      <DataBanner meta={meta} />
      <div>
        <div className="eyebrow">Settings</div>
        <h1 style={{ marginBottom: 0 }}>Settings</h1>
      </div>
      <SubscribePanel />
      <SettingsPanel
        asOf={meta ? longDate(meta.as_of) : null}
        provider={meta?.provider ?? "unknown"}
        universeCount={meta?.universe_count ?? 0}
        benchmark={meta?.benchmark ?? "—"}
        live={meta?.data_source === "live"}
      />
    </div>
  );
}

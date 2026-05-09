"use client";

import { useQuery } from "@tanstack/react-query";
import {
	Shield,
	AlertTriangle,
	AlertCircle,
	Clock,
	ExternalLink,
	CheckCircle2,
	Info,
} from "lucide-react";
import Link from "next/link";
import { cn, formatTimeAgo, formatDate } from "@/lib/utils";
import { agentApi, complianceApi } from "@/lib/api";
import type { AlertSeverity } from "@/hooks/useAgentAlerts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ComplianceAlert {
	id: string;
	severity: AlertSeverity;
	title: string;
	message: string;
	module: string;
	action_url?: string;
	action_label?: string;
	created_at: string;
	is_read: boolean;
	days_until_due?: number;
	entity_name?: string;
}

// ---------------------------------------------------------------------------
// Placeholder data
// ---------------------------------------------------------------------------

const PLACEHOLDER_ALERTS: ComplianceAlert[] = [
	{
		id: "ca-1",
		severity: "critical",
		title: "OVERDUE: SW322 Disposal — KPJ Hospital",
		message:
			"Clinical waste batch (150 kg) is 2 days past the 180-day disposal deadline.",
		module: "compliance",
		action_url: "/compliance/scheduled-waste",
		action_label: "Take Action",
		created_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
		is_read: false,
		days_until_due: -2,
		entity_name: "SW322 – KPJ Hospital",
	},
	{
		id: "ca-2",
		severity: "warning",
		title: "SW409 Batch Disposal Due in 5 Days",
		message:
			"Contaminated absorbent materials (200 kg) from Acme Manufacturing must be disposed by 25 Jun 2025.",
		module: "compliance",
		action_url: "/compliance/scheduled-waste",
		action_label: "View Batch",
		created_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
		is_read: false,
		days_until_due: 5,
		entity_name: "SW409 – Acme Manufacturing",
	},
	{
		id: "ca-3",
		severity: "warning",
		title: "DOE Licence Renewal Due in 18 Days",
		message:
			"Scheduled waste contractor licence (DOE/SWC/2021/001) expires on 30 Jun 2025.",
		module: "compliance",
		action_url: "/compliance",
		action_label: "View Licence",
		created_at: new Date(Date.now() - 1000 * 60 * 60 * 5).toISOString(),
		is_read: false,
		days_until_due: 18,
		entity_name: "DOE Licence DOE/SWC/2021/001",
	},
	{
		id: "ca-4",
		severity: "info",
		title: "SW1 (Used Oil) Batch Approaching Limit",
		message:
			"Used oil batch from Petronas R&D (320 kg) has been in storage for 155 days. 25 days remaining.",
		module: "compliance",
		action_url: "/compliance/scheduled-waste",
		action_label: "Schedule Disposal",
		created_at: new Date(Date.now() - 1000 * 60 * 60 * 12).toISOString(),
		is_read: true,
		days_until_due: 25,
		entity_name: "SW1 – Petronas R&D",
	},
	{
		id: "ca-5",
		severity: "success",
		title: "SW408 Batch Successfully Disposed",
		message:
			"Contaminated containers batch (180 kg) from Top Glove Sdn Bhd has been disposed. Certificate issued.",
		module: "compliance",
		action_url: "/compliance/scheduled-waste",
		action_label: "View Certificate",
		created_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
		is_read: true,
		days_until_due: undefined,
		entity_name: "SW408 – Top Glove Sdn Bhd",
	},
];

// ---------------------------------------------------------------------------
// Severity config
// ---------------------------------------------------------------------------

const SEVERITY_CONFIG: Record<
	AlertSeverity,
	{
		icon: React.ElementType;
		iconClass: string;
		badgeClass: string;
		borderClass: string;
		label: string;
		dotClass: string;
	}
> = {
	critical: {
		icon: AlertCircle,
		iconClass: "text-red-400",
		badgeClass: "bg-red-50 text-red-600 border border-red-200",
		borderClass: "border-l-red-500",
		label: "Critical",
		dotClass: "bg-red-500",
	},
	warning: {
		icon: AlertTriangle,
		iconClass: "text-amber-400",
		badgeClass: "bg-amber-50 text-amber-600 border border-amber-200",
		borderClass: "border-l-amber-500",
		label: "Warning",
		dotClass: "bg-amber-400",
	},
	info: {
		icon: Info,
		iconClass: "text-brand-400",
		badgeClass: "bg-brand-50 text-brand-600 border border-brand-200",
		borderClass: "border-l-brand-500",
		label: "Info",
		dotClass: "bg-brand-400",
	},
	success: {
		icon: CheckCircle2,
		iconClass: "text-green-400",
		badgeClass: "bg-green-50 text-green-600 border border-green-200",
		borderClass: "border-l-green-500",
		label: "Success",
		dotClass: "bg-green-500",
	},
};

// ---------------------------------------------------------------------------
// Days remaining badge
// ---------------------------------------------------------------------------

function DaysBadge({ days }: { days?: number }) {
	if (days === undefined || days === null) return null;

	let className: string;
	let label: string;

	if (days < 0) {
		className = "bg-red-50 text-red-600 border border-red-200";
		label = `${Math.abs(days)}d overdue`;
	} else if (days === 0) {
		className = "bg-red-50 text-red-600 border border-red-200";
		label = "Due today";
	} else if (days <= 7) {
		className = "bg-red-50 text-red-500 border border-red-200";
		label = `${days}d left`;
	} else if (days <= 20) {
		className = "bg-amber-50 text-amber-600 border border-amber-200";
		label = `${days}d left`;
	} else {
		className = "bg-brand-50 text-brand-600 border border-brand-200";
		label = `${days}d left`;
	}

	return (
		<span
			className={cn(
				"inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold leading-none flex-shrink-0",
				className,
			)}
		>
			<Clock className="w-2.5 h-2.5" />
			{label}
		</span>
	);
}

// ---------------------------------------------------------------------------
// Alert row
// ---------------------------------------------------------------------------

interface AlertRowProps {
	alert: ComplianceAlert;
}

function AlertRow({ alert }: AlertRowProps) {
	const cfg = SEVERITY_CONFIG[alert.severity] ?? SEVERITY_CONFIG.info;
	const Icon = cfg.icon;

	return (
		<div
			className={cn(
				"flex gap-3 px-4 py-3 border-b border-gray-100 border-l-2 transition-colors duration-150",
				cfg.borderClass,
				alert.is_read
					? "opacity-60 hover:opacity-80"
					: "bg-brand-50/50 hover:bg-brand-50",
			)}
		>
			{/* Severity icon */}
			<div className="flex-shrink-0 mt-0.5">
				<Icon className={cn("w-4 h-4", cfg.iconClass)} />
			</div>

			{/* Content */}
			<div className="flex-1 min-w-0">
				{/* Header */}
				<div className="flex items-start justify-between gap-2 flex-wrap">
					<div className="flex items-center gap-2 flex-wrap min-w-0">
						<span
							className={cn(
								"inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold leading-none flex-shrink-0",
								cfg.badgeClass,
							)}
						>
							{cfg.label}
						</span>
						{!alert.is_read && (
							<span className="w-1.5 h-1.5 rounded-full bg-green-500 flex-shrink-0" />
						)}
					</div>
					<DaysBadge days={alert.days_until_due} />
				</div>

				{/* Title */}
				<p
					className={cn(
						"mt-1 text-xs leading-snug",
						alert.is_read
							? "text-gray-500 font-normal"
							: "text-gray-900 font-semibold",
					)}
				>
					{alert.title}
				</p>

				{/* Entity name */}
				{alert.entity_name && (
					<p className="mt-0.5 text-[11px] text-gray-400 truncate">
						{alert.entity_name}
					</p>
				)}

				{/* Footer */}
				<div className="mt-2 flex items-center gap-3 flex-wrap">
					<span className="text-[11px] text-gray-400">
						{formatTimeAgo(alert.created_at)}
					</span>

					{alert.action_url && alert.action_label && (
						<Link
							href={alert.action_url}
							className="inline-flex items-center gap-1 text-[11px] font-semibold text-brand-600 hover:text-brand-700 transition-colors"
						>
							{alert.action_label}
							<ExternalLink className="w-2.5 h-2.5" />
						</Link>
					)}
				</div>
			</div>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function Skeleton() {
	return (
		<div className="bg-white border border-gray-200 rounded-xl animate-pulse">
			<div className="flex items-center justify-between px-5 pt-5 pb-4 border-b border-gray-100">
				<div className="flex items-center gap-3">
					<div className="w-9 h-9 rounded-lg bg-gray-200" />
					<div className="flex flex-col gap-1.5">
						<div className="h-4 w-36 rounded bg-gray-200" />
						<div className="h-3 w-28 rounded bg-gray-200" />
					</div>
				</div>
				<div className="h-4 w-16 rounded bg-gray-200" />
			</div>
			{Array.from({ length: 4 }).map((_, i) => (
				<div
					key={i}
					className="flex gap-3 px-4 py-3 border-b border-gray-100 border-l-2 border-l-gray-200"
				>
					<div className="w-4 h-4 rounded bg-gray-200 flex-shrink-0 mt-0.5" />
					<div className="flex-1 flex flex-col gap-2">
						<div className="flex gap-2">
							<div className="h-4 w-14 rounded bg-gray-200" />
							<div className="h-4 w-12 rounded bg-gray-200" />
						</div>
						<div className="h-3.5 w-3/4 rounded bg-gray-200" />
						<div className="h-3 w-1/2 rounded bg-gray-200" />
					</div>
				</div>
			))}
		</div>
	);
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

function EmptyState() {
	return (
		<div className="flex flex-col items-center justify-center py-10 px-4 text-center">
			<div className="flex items-center justify-center w-12 h-12 rounded-full bg-green-50 border border-green-200 mb-3">
				<CheckCircle2 className="w-5 h-5 text-green-400" />
			</div>
			<p className="text-sm font-semibold text-gray-700">All Clear</p>
			<p className="text-xs text-gray-500 mt-1 leading-relaxed">
				No active compliance alerts. All SW batches are within disposal
				timelines.
			</p>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Summary stats
// ---------------------------------------------------------------------------

interface SummaryStatsProps {
	alerts: ComplianceAlert[];
}

function SummaryStats({ alerts }: SummaryStatsProps) {
	const critical = alerts.filter((a) => a.severity === "critical").length;
	const warning = alerts.filter((a) => a.severity === "warning").length;
	const unread = alerts.filter((a) => !a.is_read).length;

	return (
		<div className="flex items-center gap-3 px-5 py-3 border-b border-gray-100 bg-gray-50">
			<div className="flex items-center gap-4">
				{critical > 0 && (
					<span className="flex items-center gap-1.5 text-xs font-semibold text-red-400">
						<span className="w-2 h-2 rounded-full bg-red-500" />
						{critical} Critical
					</span>
				)}
				{warning > 0 && (
					<span className="flex items-center gap-1.5 text-xs font-semibold text-amber-400">
						<span className="w-2 h-2 rounded-full bg-amber-400" />
						{warning} Warning
					</span>
				)}
				{critical === 0 && warning === 0 && (
					<span className="flex items-center gap-1.5 text-xs font-semibold text-green-400">
						<span className="w-2 h-2 rounded-full bg-green-400" />
						No critical alerts
					</span>
				)}
			</div>
			<div className="ml-auto">
				{unread > 0 && (
					<span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-green-50 text-green-600 border border-green-200">
						{unread} new
					</span>
				)}
			</div>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function ComplianceAlerts() {
	const { data: rawEvents, isLoading } = useQuery({
		queryKey: ["compliance-alerts-widget"],
		queryFn: async () => {
			try {
				const result = await agentApi.getEvents({
					page: 1,
					page_size: 5,
					ordering: "-created_at",
					event_type: "compliance",
				});
				const alerts = (result.results ?? []) as unknown as ComplianceAlert[];
				if (alerts.length === 0) return null;
				return alerts;
			} catch {
				return null;
			}
		},
		staleTime: 2 * 60_000,
		refetchInterval: 5 * 60_000,
	});

	const { data: deadlines } = useQuery({
		queryKey: ["compliance-deadlines-widget"],
		queryFn: async () => {
			try {
				const result = await complianceApi.getDeadlines();
				return result as Record<string, unknown>[];
			} catch {
				return null;
			}
		},
		staleTime: 5 * 60_000,
	});

	if (isLoading) return <Skeleton />;

	const alerts: ComplianceAlert[] = rawEvents ?? PLACEHOLDER_ALERTS;

	// Sort: critical first, then by created_at
	const sorted = [...alerts].sort((a, b) => {
		const severityOrder: Record<AlertSeverity, number> = {
			critical: 0,
			warning: 1,
			info: 2,
			success: 3,
		};
		const sA = severityOrder[a.severity] ?? 4;
		const sB = severityOrder[b.severity] ?? 4;
		if (sA !== sB) return sA - sB;
		return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
	});

	const criticalCount = sorted.filter((a) => a.severity === "critical").length;

	return (
		<div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
			{/* Header */}
			<div className="flex items-center justify-between gap-4 px-5 pt-5 pb-4 border-b border-gray-100">
				<div className="flex items-center gap-3">
					<div
						className={cn(
							"flex items-center justify-center w-9 h-9 rounded-lg border",
							criticalCount > 0
								? "bg-red-50 border-red-200"
								: "bg-amber-50 border-amber-200",
						)}
					>
						<Shield
							className={cn(
								"w-4 h-4",
								criticalCount > 0 ? "text-red-400" : "text-amber-400",
							)}
						/>
					</div>
					<div>
						<h3 className="text-sm font-semibold text-gray-900">
							Compliance Alerts
						</h3>
						<p className="text-xs text-gray-400 mt-0.5">
							{deadlines
								? `${deadlines.length} upcoming deadline${deadlines.length !== 1 ? "s" : ""}`
								: "SW batch & regulatory deadlines"}
						</p>
					</div>
				</div>

				<Link
					href="/compliance"
					className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-900 transition-colors"
				>
					View all
					<ExternalLink className="w-3 h-3" />
				</Link>
			</div>

			{/* Summary stats bar */}
			{sorted.length > 0 && <SummaryStats alerts={sorted} />}

			{/* Alert list */}
			<div className="overflow-y-auto max-h-[360px] scrollbar-hide">
				{sorted.length === 0 ? (
					<EmptyState />
				) : (
					<div className="flex flex-col">
						{sorted.map((alert) => (
							<AlertRow key={alert.id} alert={alert} />
						))}
					</div>
				)}
			</div>

			{/* Footer */}
			<div className="px-5 py-3 border-t border-gray-100 bg-gray-50">
				<Link
					href="/compliance/scheduled-waste"
					className="flex items-center justify-center gap-2 w-full py-2 rounded-lg text-xs font-medium text-gray-500 hover:text-gray-900 hover:bg-white border border-gray-200 hover:border-gray-300 transition-all duration-150"
				>
					<Shield className="w-3.5 h-3.5" />
					Manage Scheduled Waste Batches
				</Link>
			</div>

			{/* Placeholder note */}
			{!rawEvents && (
				<p className="px-5 pb-3 text-center text-[11px] text-gray-400 italic">
					Sample data — connect to backend for live alerts
				</p>
			)}
		</div>
	);
}

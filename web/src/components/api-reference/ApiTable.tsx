import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface ApiTableColumn {
  key: string;
  label: string;
}

interface ApiTableProps {
  columns: ApiTableColumn[];
  data: Record<string, string | boolean>[];
}

export function ApiTable({ columns, data }: ApiTableProps) {
  return (
    <div className="border border-border rounded-xl overflow-hidden">
      <Table className="min-w-[400px]">
        <TableHeader>
          <TableRow className="border-border hover:bg-transparent">
            {columns.map((col) => (
              <TableHead
                key={col.key}
                className="text-xs font-semibold uppercase tracking-wider text-muted-foreground bg-secondary/30 whitespace-nowrap"
              >
                {col.label}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((row, index) => (
            <TableRow key={index} className="border-border hover:bg-secondary/20">
              {columns.map((col) => (
                <TableCell key={col.key} className="text-sm">
                  {typeof row[col.key] === "boolean" ? (
                    row[col.key] ? (
                      <span className="text-emerald-400">Required</span>
                    ) : (
                      <span className="text-muted-foreground">Optional</span>
                    )
                  ) : (
                    <span className={col.key === "field" || col.key === "key" ? "font-mono text-foreground" : ""}>
                      {row[col.key]}
                    </span>
                  )}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

import { useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { getEndpointBySlug, getGroupForEndpoint } from "@/data/api-reference";
import { ApiEndpointBlock } from "./ApiEndpointBlock";
import { ApiCodeBlock } from "./ApiCodeBlock";
import { ApiTable } from "./ApiTable";
import WaveText from "@/components/ui/wave-text";

export function ApiPageContent() {
  const params = useParams();
  const endpointSlug = params["*"] || "search-packages";
  const endpoint = getEndpointBySlug(endpointSlug);
  const group = getGroupForEndpoint(endpointSlug);

  if (!endpoint) {
    return (
      <main className="flex-1 min-w-0 px-6 lg:px-12 py-10">
        <div className="max-w-3xl">
          <h1 className="text-3xl font-bold tracking-tight text-foreground mb-4">
            Endpoint not found
          </h1>
          <p className="text-muted-foreground">
            The requested API endpoint could not be found.
          </p>
        </div>
      </main>
    );
  }

  return (
    <motion.main 
      key={endpointSlug}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
      className="flex-1 min-w-0 px-4 md:px-6 lg:px-12 pt-16 lg:pt-10 pb-10 overflow-hidden"
    >
        <div className="max-w-3xl w-full">
          {/* Breadcrumb */}
          {group && (
            <p className="text-sm text-muted-foreground mb-2">{group.title}</p>
          )}

          {/* Title */}
          <h1 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground mb-4">
            <WaveText text={endpoint.title} />
          </h1>

          {/* Short description */}
          <p className="text-muted-foreground mb-8">{endpoint.description}</p>

          {/* Long description */}
          {endpoint.longDescription && (
            <p className="text-muted-foreground mb-10 leading-relaxed">
              {endpoint.longDescription}
            </p>
          )}

          {/* Endpoint Section */}
          <section id="endpoint" className="mb-10">
            <h2 className="text-xl font-semibold text-foreground mb-4">Endpoint</h2>
            <ApiEndpointBlock method={endpoint.method} path={endpoint.path} />
          </section>

          {/* Headers Section */}
          {endpoint.headers && endpoint.headers.length > 0 && (
            <section id="headers" className="mb-10">
              <h2 className="text-xl font-semibold text-foreground mb-4">Headers</h2>
              <ApiTable
                columns={[
                  { key: "key", label: "Key" },
                  { key: "value", label: "Value" },
                  { key: "required", label: "Required" },
                ]}
                data={endpoint.headers.map((h) => ({
                  key: h.key,
                  value: h.value,
                  required: h.required,
                }))}
              />
            </section>
          )}

          {/* Request Body Section */}
          {endpoint.requestBody && endpoint.requestBody.length > 0 && (
            <section id="request-body" className="mb-10">
              <h2 className="text-xl font-semibold text-foreground mb-4">Request Body</h2>
              <ApiTable
                columns={[
                  { key: "field", label: "Field" },
                  { key: "type", label: "Type" },
                  { key: "required", label: "Required" },
                  { key: "description", label: "Description" },
                ]}
                data={endpoint.requestBody.map((b) => ({
                  field: b.field,
                  type: b.type,
                  required: b.required,
                  description: b.description,
                }))}
              />
            </section>
          )}

          {/* Response Section */}
          <section id="response" className="mb-10">
            <h2 className="text-xl font-semibold text-foreground mb-4">Response</h2>
            {endpoint.responseBody && endpoint.responseBody.length > 0 ? (
              <ApiTable
                columns={[
                  { key: "field", label: "Field" },
                  { key: "type", label: "Type" },
                  { key: "description", label: "Description" },
                ]}
                data={endpoint.responseBody.map((r) => ({
                  field: r.field,
                  type: r.type,
                  description: r.description,
                }))}
              />
            ) : (
              <p className="text-muted-foreground">No response body.</p>
            )}
          </section>

          {/* Example Usage Section */}
          {(endpoint.exampleRequest || endpoint.exampleResponse) && (
            <section id="example-usage" className="mb-10">
              <h2 className="text-xl font-semibold text-foreground mb-4">Example Usage</h2>
              
              {endpoint.exampleRequest && (
                <div className="mb-6">
                  <h3 className="text-sm font-medium text-muted-foreground mb-2">Request</h3>
                  <ApiCodeBlock>{endpoint.exampleRequest}</ApiCodeBlock>
                </div>
              )}

              {endpoint.exampleResponse && (
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-2">Response</h3>
                  <ApiCodeBlock>{endpoint.exampleResponse}</ApiCodeBlock>
                </div>
              )}
            </section>
          )}
        </div>
    </motion.main>
  );
}

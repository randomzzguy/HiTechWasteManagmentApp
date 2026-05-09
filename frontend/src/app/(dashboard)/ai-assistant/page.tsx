'use client'

import AIAssistantChat from '@/components/ai/AIAssistantChat'
import AgentStatusPanel from '@/components/ai/AgentStatusPanel'
import AgentAlertFeed from '@/components/ai/AgentAlertFeed'
import KnowledgeBaseManager from '@/components/ai/KnowledgeBaseManager'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'

export default function AIAssistantPage() {
  return (
    <div className="flex flex-col gap-6 h-full">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">AI Assistant</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Powered by Ollama · RAG-augmented with regulatory and operational knowledge
          </p>
        </div>
      </div>

      {/* Tabbed content */}
      <Tabs defaultValue="assistant" className="flex-1 flex flex-col min-h-0">
        <TabsList className="w-fit mb-4">
          <TabsTrigger value="assistant">AI Assistant</TabsTrigger>
          <TabsTrigger value="knowledge-base">Knowledge Base</TabsTrigger>
        </TabsList>

        <TabsContent value="assistant" className="flex-1 min-h-0 mt-0">
          {/* Main layout */}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 h-full min-h-0">
            {/* Chat — spans 2 columns */}
            <div className="xl:col-span-2 min-h-[500px]">
              <AIAssistantChat />
            </div>

            {/* Right sidebar */}
            <div className="flex flex-col gap-4">
              <AgentStatusPanel />
              <AgentAlertFeed />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="knowledge-base" className="flex-1 min-h-0 mt-0">
          <KnowledgeBaseManager />
        </TabsContent>
      </Tabs>
    </div>
  )
}

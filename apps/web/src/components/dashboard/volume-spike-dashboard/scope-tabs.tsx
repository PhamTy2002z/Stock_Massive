"use client"

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { SignalScope } from "@/lib/api"

/**
 * The switch between the two Signal Scopes.
 *
 * The second one is labelled "Toàn bộ Universe", never "toàn thị trường": this
 * system follows a bounded set of symbols and the label has to say which set is
 * on screen, not imply the whole exchange. How large that set is stays off the
 * interface — it bounds what the collector promises, and it is not a number the
 * reader has to reason about.
 */
export function ScopeTabs({
  scope,
  onScopeChange,
}: {
  scope: SignalScope
  onScopeChange: (scope: SignalScope) => void
}) {
  return (
    <Tabs value={scope} onValueChange={(value) => onScopeChange(value as SignalScope)}>
      <TabsList>
        <TabsTrigger value="profit_leaders">Nhóm dẫn đầu lợi nhuận</TabsTrigger>
        <TabsTrigger value="universe">Toàn bộ Universe</TabsTrigger>
      </TabsList>
    </Tabs>
  )
}

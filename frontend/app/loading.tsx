export default function Loading() {
  return (
    <div className="px-6 py-4">
      <div className="border-b border-border pb-4">
        <div className="h-5 w-28 bg-subtle" />
        <div className="mt-3 h-4 w-[320px] max-w-full bg-subtle" />
      </div>
      <div className="max-w-[820px] py-5">
        <div className="border-t border-border">
          {[0, 1, 2].map((item) => (
            <div key={item} className="grid grid-cols-[120px_1fr_80px] gap-4 border-b border-border py-4">
              <div className="h-4 bg-subtle" />
              <div className="h-4 bg-subtle" />
              <div className="h-4 bg-subtle" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

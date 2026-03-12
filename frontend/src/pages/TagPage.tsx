import { useEffect, useState } from "react";
import { createTag, deleteTag, getTags } from "../api";
import type { UserTag } from "../types";

type Props = Record<string, never>;

export default function TagPage(_props: Props) {
  const [tags, setTags] = useState<UserTag[]>([]);
  const [newName, setNewName] = useState("");
  const [newColor, setNewColor] = useState("#0f766e");
  const [adding, setAdding] = useState(false);

  async function load() {
    setTags(await getTags());
  }

  useEffect(() => { load(); }, []);

  const maxWeight = Math.max(1, ...tags.map((t) => t.weight));

  async function handleAdd() {
    if (!newName.trim()) return;
    setAdding(true);
    try {
      await createTag(newName.trim(), newColor);
      setNewName("");
      await load();
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(tagId: string) {
    await deleteTag(tagId);
    await load();
  }

  return (
    <div className="page-content">
      <h2>标签管理</h2>

      {tags.length === 0 ? (
        <div className="empty-guide">
          <p>还没有标签。运行 🚀 一键抓取 后系统会自动生成。也可以手动添加你关注的主题标签。</p>
        </div>
      ) : (
        <div className="tag-cloud-section">
          <h3>标签云</h3>
          <div className="tag-cloud">
            {tags.map((tag) => {
              const scale = 0.75 + (tag.weight / maxWeight) * 0.75;
              return (
                <button
                  key={tag.tag_id}
                  className="tag-cloud-item"
                  style={{
                    fontSize: `${scale}rem`,
                    backgroundColor: tag.color + "20",
                    color: tag.color,
                    borderColor: tag.color + "40",
                  }}
                  onClick={() => {}}
                  title={`${tag.name} (权重: ${tag.weight})`}
                >
                  {tag.name}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="tag-add-section">
        <h3>添加标签</h3>
        <div className="tag-add-row">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="输入标签名..."
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          />
          <input
            type="color"
            value={newColor}
            onChange={(e) => setNewColor(e.target.value)}
            className="color-picker"
            title="选择颜色"
          />
          <button onClick={handleAdd} disabled={adding} className="add-btn">
            {adding ? "添加中..." : "+ 添加"}
          </button>
        </div>
      </div>

      {tags.length > 0 && (
        <div className="tag-table-section">
          <h3>标签列表</h3>
          <table className="tag-table">
            <thead>
              <tr>
                <th>颜色</th>
                <th>名称</th>
                <th>权重</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {tags.map((tag) => (
                <tr key={tag.tag_id}>
                  <td><span className="color-dot" style={{ backgroundColor: tag.color }} /></td>
                  <td>{tag.name}</td>
                  <td>{tag.weight}</td>
                  <td>
                    <button className="delete-btn" onClick={() => handleDelete(tag.tag_id)} aria-label={`删除 ${tag.name}`}>
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

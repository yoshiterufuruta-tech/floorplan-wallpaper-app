"use client";

import { useRef, useState } from "react";

export default function Home() {
  const canvasRef = useRef(null);
  const [result, setResult] = useState(null);

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(
      "https://YOUR_BACKEND_ON_RENDER.onrender.com/analyze_floorplan",
      {
        method: "POST",
        body: formData,
      }
    );

    const json = await res.json();
    setResult(json);

    const img = new Image();
    img.src = URL.createObjectURL(file);
    img.onload = () => drawCanvas(img, json);
  };

  const drawCanvas = (img, data) => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");

    canvas.width = img.width;
    canvas.height = img.height;

    ctx.drawImage(img, 0, 0);

    // 壁線（赤）
    ctx.strokeStyle = "red";
    ctx.lineWidth = 2;
    data.wall_lines.forEach(([x1, y1, x2, y2]) => {
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    });

    // 開口部（青）
    ctx.strokeStyle = "blue";
    ctx.lineWidth = 3;
    data.openings.forEach((op) => {
      const { x1, y1, x2, y2 } = op.opening;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
    });

    // 寸法（緑）
    ctx.fillStyle = "green";
    ctx.font = "20px Arial";
    data.dimensions.forEach((dim) => {
      ctx.fillText(dim.text, dim.x, dim.y);
    });
  };

  return (
    <div>
      <h2>図面アップロード（壁線＋開口部＋寸法の完全可視化）</h2>
      <input type="file" onChange={handleUpload} />
      <canvas ref={canvasRef} style={{ border: "1px solid #ccc", marginTop: 20 }} />
      <pre>{result && JSON.stringify(result.result, null, 2)}</pre>
    </div>
  );
}

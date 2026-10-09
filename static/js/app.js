document.addEventListener("DOMContentLoaded", () => {
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";

  const assistantForm = document.querySelector("#assistant-form");
  if (assistantForm) {
    assistantForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const box = document.querySelector("#assistant-result");
      const input = document.querySelector("#assistant-input");
      const message = input?.value.trim();
      if (!box || !message) return;
      box.textContent = "Yours AI is checking the live catalog…";
      try {
        const response = await fetch("/api/assistant", {
          method: "POST",
          headers: {"Content-Type": "application/json", "X-CSRFToken": csrf},
          body: JSON.stringify({message})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "The assistant is unavailable. Please retry.");
        const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
          "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
        })[char]);
        box.innerHTML = "<p>" + escape(data.reply) + "</p><div class='grid'>" +
          (Array.isArray(data.products) ? data.products.slice(0, 3) : []).map((product) =>
            "<a class='product-card' href='/product/" + encodeURIComponent(product.slug || "") +
            "'><img class='image-wrap' src='" + escape(product.image_url || "") +
            "' alt=''><div class='pc-body'><b>" + escape(product.name) +
            "</b><div>Rs. " + Number(product.price || 0).toLocaleString() +
            "</div></div></a>").join("") + "</div>";
      } catch (error) {
        box.textContent = error.message || "The assistant is unavailable. Please retry.";
      }
    });
  }

  document.querySelectorAll("form").forEach((form) => {
    if (!form.querySelector('input[name="_csrf"]') && csrf) {
      const field = document.createElement("input");
      field.type = "hidden";
      field.name = "_csrf";
      field.value = csrf;
      form.appendChild(field);
    }
  });

  const checkoutForm = document.querySelector("#checkout-form");
  if (checkoutForm) {
    checkoutForm.addEventListener("submit", (event) => {
      if (checkoutForm.dataset.submitting === "true") {
        event.preventDefault();
        return;
      }
      if (!checkoutForm.reportValidity()) {
        event.preventDefault();
        return;
      }
      checkoutForm.dataset.submitting = "true";
      const submit = document.querySelector("#checkout-submit");
      if (submit) {
        submit.disabled = true;
        submit.textContent = "Submitting your order…";
      }
    });
  }

  const addressSelect = document.querySelector("#saved-address");
  if (addressSelect) {
    addressSelect.addEventListener("change", () => {
      const option = addressSelect.selectedOptions[0];
      if (!option || !option.value) return;
      const fields = {
        full_name: "name", phone: "phone", province: "province", area: "area",
        address: "address", city: "city", postal_code: "postal", instructions: "instructions"
      };
      Object.entries(fields).forEach(([field, attr]) => {
        const input = document.querySelector('[name="' + field + '"]');
        if (input) input.value = option.dataset[attr] || "";
      });
    });
  }

  const fileInput = document.querySelector("#photo");
  const preview = document.querySelector("#preview");
  if (fileInput && preview) {
    fileInput.addEventListener("change", () => {
      const file = fileInput.files?.[0];
      if (!file) return;
      if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 8 * 1024 * 1024) {
        alert("Please choose a JPG, PNG or WebP under 8MB.");
        fileInput.value = "";
        preview.removeAttribute("src");
        preview.classList.add("hidden");
        return;
      }
      preview.src = URL.createObjectURL(file);
      preview.classList.remove("hidden");
    });
  }

  const tryOnForm = document.querySelector("#tryon-form");
  if (tryOnForm) {
    tryOnForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = document.querySelector("#tryon-submit");
      const status = document.querySelector("#tryon-status");
      if (!button || !status) return;
      button.disabled = true;
      button.textContent = "AI is processing…";
      status.textContent = "Preparing your private try-on request…";
      try {
        const response = await fetch("/api/tryon/" + encodeURIComponent(tryOnForm.dataset.product), {
          method: "POST", body: new FormData(tryOnForm)
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Try-on failed.");
        let attempts = 0;
        const poll = async () => {
          const resultResponse = await fetch("/api/tryon/status/" + encodeURIComponent(data.job_id));
          const result = await resultResponse.json();
          if (!resultResponse.ok) throw new Error(result.error || "Unable to check try-on status.");
          if (result.status === "completed") {
            const outputUrl = new URL(result.output);
            if (outputUrl.protocol !== "https:" && outputUrl.protocol !== "http:") {
              throw new Error("The AI provider returned an invalid image link.");
            }
            status.replaceChildren();
            const message = document.createElement("p");
            message.className = "success";
            message.textContent = "Your AI try-on is ready.";
            const link = document.createElement("a");
            link.className = "btn dark";
            link.href = outputUrl.href;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = "Open generated look";
            const image = document.createElement("img");
            image.className = "preview";
            image.src = outputUrl.href;
            image.alt = "AI try-on result";
            status.append(message, link, image);
            button.textContent = "Generate again";
            button.disabled = false;
          } else if (result.status === "failed") {
            throw new Error(result.error || "The AI provider could not complete this request.");
          } else {
            attempts += 1;
            status.textContent = "AI status: " + String(result.status || "processing") + "…";
            if (attempts > 45) throw new Error("The generation is taking too long. Please retry.");
            await new Promise((resolve) => setTimeout(resolve, 2000));
            await poll();
          }
        };
        await poll();
      } catch (error) {
        const message = document.createElement("div");
        message.className = "alert";
        message.textContent = error.message || "Try-on failed. Please retry.";
        status.replaceChildren(message);
        button.disabled = false;
        button.textContent = "Try again";
      }
    });
  }
});

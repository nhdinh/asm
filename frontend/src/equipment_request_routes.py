# Equipment Request Routes
from flask import render_template, request, redirect, url_for, flash, jsonify, session
from api_client import ApiClient


def register_equipment_request_routes(app, get_api_client_func, login_required):
    """Register all equipment request routes"""

    @app.route("/equipment-requests")
    @login_required
    def equipment_requests():
        """List equipment requests"""
        try:
            client = get_api_client_func()
            page = request.args.get("page", 1, type=int)
            per_page = request.args.get("per_page", 20, type=int)
            status_filter = request.args.get("status", "")

            params = {"page": page, "per_page": per_page}
            if status_filter:
                params["status"] = status_filter

            response = client.session.get(
                f"{client.base_url}/equipment-requests", params=params
            )

            if response.status_code == 200:
                data = response.json()
                requests_list = data.get("requests", [])
                total = data.get("total", 0)
                pages = data.get("pages", 1)

                return render_template(
                    "equipment_requests/list.html",
                    requests=requests_list,
                    total=total,
                    page=page,
                    per_page=per_page,
                    pages=pages,
                    status_filter=status_filter,
                    total_count=total,
                )
            else:
                flash("Không thể tải danh sách yêu cầu", "danger")
                return render_template(
                    "equipment_requests/list.html",
                    requests=[],
                    total=0,
                    page=1,
                    per_page=20,
                    pages=1,
                    status_filter="",
                    total_count=0,
                )
        except Exception as e:
            app.logger.error(f"Error loading equipment requests: {str(e)}")
            flash(f"Lỗi: {str(e)}", "danger")
            return render_template(
                "equipment_requests/list.html",
                requests=[],
                total=0,
                page=1,
                per_page=20,
                pages=1,
                status_filter="",
                total_count=0,
            )

    @app.route("/equipment-requests/create", methods=["GET", "POST"])
    @login_required
    def equipment_request_create():
        """Create new equipment request"""
        client = get_api_client_func()

        if request.method == "POST":
            try:
                data = request.json
                response = client.session.post(
                    f"{client.base_url}/equipment-requests", json=data
                )

                if response.status_code in [200, 201]:
                    return jsonify(response.json()), response.status_code
                else:
                    return (
                        jsonify(response.json() if response.content else {"error": "Failed to create request"}),
                        response.status_code,
                    )
            except Exception as e:
                app.logger.error(f"Error creating equipment request: {str(e)}")
                return jsonify({"error": str(e)}), 500

        # GET - show create form
        try:
            # Get user's departments
            user = session.get("user", {})
            user_departments = user.get("departments", [])

            # Get categories for dropdown
            categories_response = client.get_categories()
            if isinstance(categories_response, dict) and "items" in categories_response:
                categories = categories_response["items"]
            else:
                categories = categories_response if categories_response else []

            return render_template(
                "equipment_requests/create.html",
                user_departments=user_departments,
                categories=categories,
            )
        except Exception as e:
            app.logger.error(f"Error loading create form: {str(e)}")
            flash(f"Lỗi: {str(e)}", "danger")
            return redirect(url_for("equipment_requests"))

    @app.route("/equipment-requests/<int:request_id>")
    @login_required
    def equipment_request_detail(request_id):
        """View equipment request details"""
        try:
            client = get_api_client_func()
            response = client.session.get(
                f"{client.base_url}/equipment-requests/{request_id}"
            )

            if response.status_code == 200:
                eq_request = response.json()
                return render_template(
                    "equipment_requests/detail.html", request=eq_request
                )
            else:
                flash("Không thể tải chi tiết yêu cầu", "danger")
                return redirect(url_for("equipment_requests"))
        except Exception as e:
            app.logger.error(f"Error loading equipment request: {str(e)}")
            flash(f"Lỗi: {str(e)}", "danger")
            return redirect(url_for("equipment_requests"))

    @app.route("/equipment-requests/<int:request_id>/edit", methods=["GET", "POST"])
    @login_required
    def equipment_request_edit(request_id):
        """Edit equipment request (only DRAFT status)"""
        client = get_api_client_func()

        if request.method == "POST":
            try:
                data = request.json
                response = client.session.put(
                    f"{client.base_url}/equipment-requests/{request_id}", json=data
                )

                if response.status_code == 200:
                    return jsonify(response.json()), 200
                else:
                    return jsonify(response.json() if response.content else {"error": "Failed to update"}), response.status_code
            except Exception as e:
                app.logger.error(f"Error updating equipment request: {str(e)}")
                return jsonify({"error": str(e)}), 500

        # GET - show edit form
        try:
            response = client.session.get(
                f"{client.base_url}/equipment-requests/{request_id}"
            )

            if response.status_code == 200:
                eq_request = response.json()

                # Get user's departments
                user = session.get("user", {})
                user_departments = user.get("departments", [])

                # Get categories
                categories_response = client.get_categories()
                if isinstance(categories_response, dict) and "items" in categories_response:
                    categories = categories_response["items"]
                else:
                    categories = categories_response if categories_response else []

                return render_template(
                    "equipment_requests/edit.html",
                    request=eq_request,
                    user_departments=user_departments,
                    categories=categories,
                )
            else:
                flash("Không thể tải yêu cầu", "danger")
                return redirect(url_for("equipment_requests"))
        except Exception as e:
            app.logger.error(f"Error loading equipment request for edit: {str(e)}")
            flash(f"Lỗi: {str(e)}", "danger")
            return redirect(url_for("equipment_requests"))

    @app.route("/equipment-requests/<int:request_id>/sign", methods=["POST"])
    @login_required
    def equipment_request_sign(request_id):
        """Sign equipment request"""
        try:
            client = get_api_client_func()
            data = request.json
            response = client.session.post(
                f"{client.base_url}/equipment-requests/{request_id}/sign", json=data
            )

            if response.status_code == 200:
                return jsonify(response.json()), 200
            else:
                return jsonify(response.json() if response.content else {"error": "Failed to sign"}), response.status_code
        except Exception as e:
            app.logger.error(f"Error signing equipment request: {str(e)}")
            return jsonify({"error": str(e)}), 500

    @app.route("/equipment-requests/<int:request_id>/approve", methods=["POST"])
    @login_required
    def equipment_request_approve(request_id):
        """Approve equipment request (manager)"""
        try:
            client = get_api_client_func()
            data = request.json
            response = client.session.post(
                f"{client.base_url}/equipment-requests/{request_id}/approve", json=data
            )

            if response.status_code == 200:
                return jsonify(response.json()), 200
            else:
                return jsonify(response.json() if response.content else {"error": "Failed to approve"}), response.status_code
        except Exception as e:
            app.logger.error(f"Error approving equipment request: {str(e)}")
            return jsonify({"error": str(e)}), 500

    @app.route("/equipment-requests/<int:request_id>/reject", methods=["POST"])
    @login_required
    def equipment_request_reject(request_id):
        """Reject equipment request (manager)"""
        try:
            client = get_api_client_func()
            data = request.json
            response = client.session.post(
                f"{client.base_url}/equipment-requests/{request_id}/reject", json=data
            )

            if response.status_code == 200:
                return jsonify(response.json()), 200
            else:
                return jsonify(response.json() if response.content else {"error": "Failed to reject"}), response.status_code
        except Exception as e:
            app.logger.error(f"Error rejecting equipment request: {str(e)}")
            return jsonify({"error": str(e)}), 500

    @app.route("/equipment-requests/<int:request_id>/process", methods=["POST"])
    @login_required
    def equipment_request_process(request_id):
        """Process equipment request (HR/Admin)"""
        try:
            client = get_api_client_func()
            data = request.json
            response = client.session.post(
                f"{client.base_url}/equipment-requests/{request_id}/process", json=data
            )

            if response.status_code == 200:
                return jsonify(response.json()), 200
            else:
                return jsonify(response.json() if response.content else {"error": "Failed to process"}), response.status_code
        except Exception as e:
            app.logger.error(f"Error processing equipment request: {str(e)}")
            return jsonify({"error": str(e)}), 500

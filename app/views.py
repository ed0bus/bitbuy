from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from .models import Profile, Order
from django.contrib import messages
from .forms import OrderForm
from django.http import JsonResponse
import json
from django.core import serializers
import random
from bson.objectid import ObjectId


def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get("username")
            password1 = form.cleaned_data.get("password1")
            user = authenticate(username=username, password=password1)
            login(request, user)
            Profile.objects.create(
                nickname=username,
                usd_balance=round(random.uniform(100.0, 100000.0), 2),
                btc_balance=round(random.uniform(1.0, 10.0), 2),
            )
            login(request, user)
            return redirect(place_order)
        else:
            return render(request, "signup.html", {"form": form})
    else:
        form = UserCreationForm()
        return render(request, "signup.html", {"form": form})


def signin(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(place_order)
        else:
            messages.warning(request, "This user is not registered!")
            return render(request, "login.html")
    else:
        return render(request, "login.html")


def place_order(request):
    try:
        # associate current user and profile
        current_user = request.user.username
        customer = Profile.objects.get(nickname=current_user)
        form = OrderForm(
            initial={
                "btc_balance": customer.btc_balance,
                "usd_balance": customer.usd_balance,
            }
        )
        context = {"form": form}

        if request.method == "POST":
            form = OrderForm(request.POST)
            if form.is_valid():
                quantity = form.cleaned_data["quantity"]
                price = form.cleaned_data["price"]
                order_type = form.cleaned_data["action"]
                pending_orders_btc = sum(
                    Order.objects.filter(
                        profile=current_user, order_status="OPENED", order_type="SELL"
                    ).values_list("quantity", flat=True)
                )  # sum of current user totals btc pending in sell orders
                pending_orders_usd = sum(
                    [
                        item.price * item.quantity
                        for item in Order.objects.filter(
                            profile=current_user,
                            order_status="OPENED",
                            order_type="BUY",
                        )
                    ]
                )  # sum of current user total usd pending in buy orders

                if (
                    order_type == "SELL"
                    and quantity < customer.btc_balance
                    and quantity < (customer.btc_balance - pending_orders_btc)
                    and quantity > 0
                ):
                    # create a new order first using the form: the order is added to the djongo database
                    new_order = Order.objects.create(
                        quantity=quantity,
                        price=price,
                        profile=customer,
                        order_type=order_type,
                        order_status="OPENED",
                    )
                    messages.success(
                        request,
                        "Orders successfully created.. Your Order has been added to the order book",
                    )
                    # three possible conditions for SELL order
                    while new_order.order_status == "OPENED":
                        # make a new query everytime the new order is opened to check if there's a matching open order based on price priority
                        matching_buy_order = (
                            Order.objects.filter(
                                price__gte=price,
                                order_type="BUY",
                                order_status="OPENED",
                            )
                            .order_by("-price")
                            .first()
                        )

                        if round(matching_buy_order.quantity, 1) == round(
                            new_order.quantity, 1
                        ):
                            new_order.order_status = "CLOSED"
                            new_order.price = matching_buy_order.price
                            new_order.save(update_fields=["order_status", "price"])
                            matching_buy_order.order_status = "CLOSED"
                            matching_buy_order.save(update_fields=["order_status"])
                            # update balances
                            y = matching_buy_order.profile_id  # find buyer nickname
                            customer.usd_balance = customer.usd_balance + (
                                quantity * new_order.price
                            )
                            customer.btc_balance -= quantity
                            customer.save(update_fields=["usd_balance", "btc_balance"])
                            buyer = Profile.objects.get(nickname=y)
                            buyer.usd_balance = buyer.usd_balance - (
                                quantity * matching_buy_order.price
                            )
                            buyer.btc_balance += quantity
                            buyer.save(update_fields=["usd_balance", "btc_balance"])
                            messages.success(
                                request, "Matching sell order found ... Order Completed"
                            )

                        if (
                            new_order.quantity < matching_buy_order.quantity
                            and new_order.order_status == "OPENED"
                        ):
                            new_order.order_status = "CLOSED"
                            new_order.price = matching_buy_order.price
                            new_order.save(update_fields=["order_status", "price"])
                            # save matching buy order with more quantity
                            matching_buy_order.quantity = (
                                matching_buy_order.quantity - new_order.quantity
                            )
                            matching_buy_order.save(update_fields=["quantity"])

                            y = matching_buy_order.profile_id
                            customer.usd_balance = (
                                customer.usd_balance
                                + new_order.quantity * new_order.price
                            )
                            customer.btc_balance = (
                                customer.btc_balance - new_order.quantity
                            )
                            customer.save(update_fields=["usd_balance", "btc_balance"])
                            buyer = Profile.objects.get(nickname=y)
                            # create a closed order for the buyer with the filled quantity
                            Order.objects.create(
                                quantity=new_order.quantity,
                                price=new_order.price,
                                profile=buyer,
                                order_type="BUY",
                                order_status="CLOSED",
                            )
                            buyer.usd_balance = buyer.usd_balance - (
                                new_order.quantity * new_order.price
                            )
                            buyer.btc_balance = buyer.btc_balance + new_order.quantity
                            buyer.save(update_fields=["usd_balance", "btc_balance"])
                            messages.success(
                                request, "Matching sell order found ... Order Completed"
                            )

                        if (
                            new_order.quantity > matching_buy_order.quantity
                            and new_order.order_status == "OPENED"
                        ):
                            new_order.quantity = (
                                new_order.quantity - matching_buy_order.quantity
                            )
                            new_order.save(update_fields=["quantity"])
                            # close matching buy order with less quantity
                            matching_buy_order.order_status = "CLOSED"
                            matching_buy_order.save(update_fields=["order_status"])
                            # create a closed order for the seller with the filled quantity by the buyer
                            filled_order = Order.objects.create(
                                quantity=matching_buy_order.quantity,
                                price=matching_buy_order.price,
                                profile=customer,
                                order_type="SELL",
                                order_status="CLOSED",
                            )
                            y = matching_buy_order.profile_id

                            customer.usd_balance = (
                                customer.usd_balance
                                + filled_order.quantity * filled_order.price
                            )
                            customer.btc_balance -= filled_order.quantity
                            customer.save(update_fields=["usd_balance", "btc_balance"])
                            buyer = Profile.objects.get(nickname=y)
                            buyer.usd_balance = buyer.usd_balance - (
                                matching_buy_order.quantity * matching_buy_order.price
                            )
                            buyer.btc_balance += matching_buy_order.quantity
                            buyer.save(update_fields=["usd_balance", "btc_balance"])
                            messages.success(
                                request, "Matching sell order found ... Order Completed"
                            )

                elif (
                    order_type == "BUY"
                    and customer.usd_balance > price * quantity
                    and (price * quantity) < (customer.usd_balance - pending_orders_usd)
                    and quantity > 0
                ):
                    new_order = Order.objects.create(
                        quantity=quantity,
                        price=price,
                        profile=customer,
                        order_type=order_type,
                        order_status="OPENED",
                    )
                    messages.success(
                        request,
                        "Orders successfully created.. Your Order has been added to the order book",
                    )
                    # three possible conditions for BUY order
                    while new_order.order_status == "OPENED":
                        matching_sell_order = (
                            Order.objects.filter(
                                price__lte=price,
                                order_type="SELL",
                                order_status="OPENED",
                            )
                            .order_by("-price")
                            .last()
                        )
                        # if quantity is equal
                        if round(new_order.quantity, 1) == round(
                            matching_sell_order.quantity, 1
                        ):
                            new_order.order_status = "CLOSED"
                            new_order.price = matching_sell_order.price
                            new_order.save(update_fields=["order_status", "price"])
                            matching_sell_order.order_status = "CLOSED"
                            matching_sell_order.save(update_fields=["order_status"])
                            y = matching_sell_order.profile_id  # find seller

                            customer.usd_balance = (
                                customer.usd_balance - quantity * new_order.price
                            )
                            customer.btc_balance += quantity
                            customer.save(update_fields=["usd_balance", "btc_balance"])
                            seller = Profile.objects.get(nickname=y)
                            seller.usd_balance = (
                                seller.usd_balance
                                + quantity * matching_sell_order.price
                            )
                            seller.btc_balance -= quantity
                            seller.save(update_fields=["usd_balance", "btc_balance"])
                            messages.success(
                                request,
                                "Matching sell order with same quantity found ... Order Completed",
                            )
                        # if quantity is minor
                        if (
                            new_order.quantity < matching_sell_order.quantity
                            and new_order.order_status == "OPENED"
                        ):
                            new_order.order_status = "CLOSED"
                            new_order.price = matching_sell_order.price
                            new_order.save(update_fields=["order_status", "price"])
                            matching_sell_order.quantity = round(
                                (matching_sell_order.quantity - new_order.quantity), 2
                            )
                            matching_sell_order.save(update_fields=["quantity"])
                            seller_nickname = (
                                matching_sell_order.profile_id
                            )  # equal to seller name
                            customer.usd_balance = (
                                customer.usd_balance
                                - new_order.quantity * new_order.price
                            )
                            customer.btc_balance += new_order.quantity
                            customer.save(update_fields=["usd_balance", "btc_balance"])
                            seller = Profile.objects.get(nickname=seller_nickname)
                            filled_sell = Order.objects.create(
                                quantity=new_order.quantity,
                                price=new_order.price,
                                profile=seller,
                                order_type="SELL",
                                order_status="CLOSED",
                            )
                            seller.usd_balance = (
                                seller.usd_balance
                                + filled_sell.quantity * filled_sell.price
                            )
                            seller.btc_balance -= filled_sell.quantity
                            seller.save(update_fields=["usd_balance", "btc_balance"])
                            messages.success(
                                request,
                                "Matching sell order found ... Your order is completed!",
                            )

                        if (
                            new_order.quantity > matching_sell_order.quantity
                            and new_order.order_status == "OPENED"
                        ):
                            new_order.quantity = round(
                                new_order.quantity - matching_sell_order.quantity, 2
                            )
                            new_order.save(update_fields=["quantity"])
                            matching_sell_order.order_status = "CLOSED"
                            matching_sell_order.save(
                                update_fields=["order_status", "price"]
                            )
                            seller_nickname = matching_sell_order.profile_id
                            filled_order = Order.objects.create(
                                quantity=matching_sell_order.quantity,
                                price=matching_sell_order.price,
                                profile=customer,
                                order_type="BUY",
                                order_status="CLOSED",
                            )
                            customer.usd_balance = (
                                customer.usd_balance
                                - filled_order.quantity * filled_order.price
                            )
                            customer.btc_balance += filled_order.quantity
                            customer.save(update_fields=["usd_balance", "btc_balance"])
                            seller = Profile.objects.get(nickname=seller_nickname)

                            seller.usd_balance = (
                                seller.usd_balance
                                + matching_sell_order.quantity
                                * matching_sell_order.price
                            )
                            seller.btc_balance = (
                                seller.btc_balance - matching_sell_order.quantity
                            )
                            seller.save(update_fields=["usd_balance", "btc_balance"])
                            messages.success(
                                request,
                                "Matching sell order found ... Part of your order is completed",
                            )

                else:
                    if quantity < 0:
                        messages.success(
                            request,
                            "You can not fill an order with negative quantity! Change your amount.",
                        )
                    else:
                        messages.success(request, "Your balance is insufficient!")

        return render(request, "orders.html", context)

    except:
        # profile is not created for admin user
        if request.user.is_authenticated and request.user.is_superuser:
            messages.warning(
                request, "You are not able to place an order as admin user!"
            )
            return render(request, "orders.html")
        # user is not logged in
        elif request.user.is_authenticated is False:
            return render(request, "orders.html")
        # user is autheticated but profile has been deleted or blocked by administrator
        elif (
            request.user.is_authenticated
            and Profile.objects.filter(nickname=current_user).exists() is False
        ):
            messages.warning(
                request,
                "Your profile has been deleted by an admin or temporarly blocked, try to send a ticket for further "
                "informations!",
            )
            return render(request, "orders.html")
        # else return new form with updated balances
        else:
            return render(request, "orders.html", context)


def orderbook(request):
    orders = Order.objects.filter(order_status="OPENED")
    data = serializers.serialize("json", orders)
    pretty_json = json.loads(data.replace("'", ""))
    return JsonResponse(pretty_json, safe=False)


# Orders overview
def overview(request):
    try:
        current_user = request.user.username
        customer = Profile.objects.get(nickname=current_user)
        btc_balance = customer.btc_balance  # actual btc balance
        usd_balance = customer.usd_balance  # actual usd balance
        usd_spent = sum(
            [
                item.price * item.quantity
                for item in Order.objects.filter(
                    profile=current_user, order_status="CLOSED", order_type="BUY"
                )
            ]
        )  # spent money usd trough buy orders
        btc_acquired = sum(
            Order.objects.filter(
                profile=current_user, order_status="CLOSED", order_type="BUY"
            ).values_list("quantity", flat=True)
        )
        btc_sold = sum(
            Order.objects.filter(
                profile=current_user, order_status="CLOSED", order_type="SELL"
            ).values_list("quantity", flat=True)
        )
        usd_obtained = sum(
            [
                item.price * item.quantity
                for item in Order.objects.filter(
                    profile=current_user, order_status="CLOSED", order_type="SELL"
                )
            ]
        )

        initial_btc_balance = round((btc_balance + btc_sold - btc_acquired), 2)
        initial_usd_balance = round((usd_balance + usd_spent - usd_obtained), 2)
        btc_gains_prc = (
            str(
                round(
                    (btc_balance - initial_btc_balance) / initial_btc_balance * 100, 2
                )
            )
            + " %"
        )
        usd_gains_prc = (
            str(
                round(
                    (usd_balance - initial_usd_balance) / initial_usd_balance * 100, 2
                )
            )
            + " %"
        )
        usd_gains = round((usd_balance - initial_usd_balance), 2)
        btc_gains = round((btc_balance - initial_btc_balance), 2)

        open_orders = Order.objects.filter(order_status="OPENED", profile=current_user)
        closed_orders = Order.objects.filter(
            order_status="CLOSED", profile=current_user
        )

        return render(
            request,
            "overview.html",
            {
                "open_orders": open_orders,
                "closed_orders": closed_orders,
                "usd_gains_prc": usd_gains_prc,
                "btc_gains_prc": btc_gains_prc,
                "usd_gains": usd_gains,
                "btc_gains": btc_gains,
                "initial_btc": initial_btc_balance,
                "initial_usd": initial_usd_balance,
                "actual_usd": usd_balance,
                "actual_btc": btc_balance,
            },
        )
    except:
        return render(request, "overview.html")


# Delete an order
def delete_order(request, order_id):
    order = Order.objects.get(pk=ObjectId(order_id))
    order.delete()
    return redirect("overview")
